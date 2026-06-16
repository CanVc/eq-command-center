from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from eqmarket.api.app import create_app


class ApiAppTests(unittest.TestCase):
    def test_health_returns_ok_and_visible_db_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "eqmarket.sqlite"
            app = create_app(db_path)

            with TestClient(app) as client:
                response = client.get("/api/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                {
                    "status": "ok",
                    "db_path": str(db_path.resolve()),
                },
            )
