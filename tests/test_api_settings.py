from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app
from eqmarket.db import init_db


class ApiSettingsTests(unittest.TestCase):
    def test_settings_status_returns_db_server_and_log_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            init_db(db_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/settings/status", params={"server": "Mischief"})

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["db_path"], str(db_path.resolve()))
            self.assertEqual(payload["default_server"], "frostreaver")
            self.assertEqual(payload["active_server"], "mischief")
            self.assertIsNone(payload["eq_log_path"])
            self.assertIsNone(payload["eq_log_exists"])
            self.assertIsNone(payload["eq_log_import_state"])
            self.assertIsNone(payload["log_settings_error"])
            self.assertNotIn("recent_tlp_errors", payload)

    def test_settings_status_still_reports_db_path_when_log_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "missing.sqlite"
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/settings/status")

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["db_path"], str(db_path.resolve()))
            self.assertEqual(payload["active_server"], "frostreaver")
            self.assertIsNone(payload["eq_log_path"])
            self.assertIsInstance(payload["log_settings_error"], str)

    def test_log_path_can_be_saved_and_reported_with_import_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            log_path = temp_path / "eqlog_Dreadbank_frostreaver.txt"
            log_path.write_text("auction line\n", encoding="utf-8")
            init_db(db_path)
            _seed_log_import_state(db_path, log_path)
            app = create_app(db_path)

            with TestClient(app) as client:
                update_response = client.put(
                    "/api/settings/log-path",
                    params={"server": "Frostreaver"},
                    json={"log_path": str(log_path)},
                )
                status_response = client.get("/api/settings/status", params={"server": "frostreaver"})

            self.assertEqual(update_response.status_code, 200, update_response.text)
            update_payload = update_response.json()
            self.assertEqual(update_payload["eq_log_path"], str(log_path.resolve()))
            self.assertTrue(update_payload["eq_log_exists"])
            self.assertEqual(update_payload["eq_log_import_state"]["last_position"], 123)

            self.assertEqual(status_response.status_code, 200, status_response.text)
            status_payload = status_response.json()
            self.assertEqual(status_payload["eq_log_path"], str(log_path.resolve()))
            self.assertTrue(status_payload["eq_log_exists"])
            self.assertIsNone(status_payload["log_settings_error"])

    def test_log_path_can_be_selected_with_native_picker_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "eqmarket.sqlite"
            log_path = temp_path / "eqlog_Dreadbank_frostreaver.txt"
            log_path.write_text("auction line\n", encoding="utf-8")
            init_db(db_path)
            app = create_app(db_path)

            with patch(
                "eqmarket.api.routes.settings.choose_eq_log_path",
                return_value=str(log_path),
            ) as choose_log_path:
                with TestClient(app) as client:
                    response = client.post(
                        "/api/settings/log-path/browse",
                        params={"server": "Frostreaver"},
                    )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["eq_log_path"], str(log_path.resolve()))
            self.assertTrue(payload["eq_log_exists"])
            choose_log_path.assert_called_once_with(None)


def _seed_log_import_state(db_path: Path, log_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO log_import_state (
                log_path, server, file_size, file_mtime, last_position, updated_at
            ) VALUES (?, 'frostreaver', 456, 789.0, 123, '2026-06-16 10:00:00')
            """,
            (str(log_path.resolve()),),
        )
        connection.commit()


if __name__ == "__main__":
    unittest.main()
