from __future__ import annotations

from contextlib import closing
import sqlite3
from pathlib import Path


ITEMS_TABLE_NAME = "items"
ITEMS_REBUILD_TABLE_NAME = "items__without_name_uniques"


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "docs" / "data-model" / "data-model.sql"


def init_db(db_path: Path) -> None:
    """Create or update the local SQLite database using the SQL schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_sql)
        connection.commit()

        if _items_table_has_name_uniques(connection):
            _rebuild_items_table_without_name_uniques(connection, schema_sql)
            # Re-run the schema so indexes dropped with the old items table are recreated.
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema_sql)

        connection.commit()


def _items_table_has_name_uniques(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (ITEMS_TABLE_NAME,),
    ).fetchone()
    if row is None:
        return False

    for index in connection.execute(f"PRAGMA index_list('{ITEMS_TABLE_NAME}')").fetchall():
        # PRAGMA index_list: seq, name, unique, origin, partial.
        is_unique = bool(index[2])
        if not is_unique:
            continue
        index_name = str(index[1])
        columns = {
            str(column[2])
            for column in connection.execute(f"PRAGMA index_info('{index_name}')").fetchall()
            if column[2] is not None
        }
        if columns & {"name", "normalized_name"}:
            return True
    return False


def _rebuild_items_table_without_name_uniques(connection: sqlite3.Connection, schema_sql: str) -> None:
    """Drop legacy UNIQUE(name/normalized_name) constraints from items safely.

    SQLite cannot remove column UNIQUE constraints in place. Rebuild the parent
    table while foreign key enforcement is disabled, then validate all child
    references before returning.
    """
    connection.commit()
    create_sql = _items_create_table_sql(schema_sql, ITEMS_REBUILD_TABLE_NAME)
    source_columns = _table_columns(connection, ITEMS_TABLE_NAME)

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute(f"DROP TABLE IF EXISTS {ITEMS_REBUILD_TABLE_NAME}")
        connection.execute(create_sql)
        target_columns = _table_columns(connection, ITEMS_REBUILD_TABLE_NAME)
        copy_columns = [column for column in source_columns if column in target_columns]
        quoted_columns = ", ".join(_quote_identifier(column) for column in copy_columns)
        connection.execute(
            f"""
            INSERT INTO {ITEMS_REBUILD_TABLE_NAME} ({quoted_columns})
            SELECT {quoted_columns}
            FROM {ITEMS_TABLE_NAME}
            """
        )
        connection.execute(f"DROP TABLE {ITEMS_TABLE_NAME}")
        connection.execute(f"ALTER TABLE {ITEMS_REBUILD_TABLE_NAME} RENAME TO {ITEMS_TABLE_NAME}")
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (2, 'Allow duplicate item display names; item_id is canonical')
            """
        )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError(f"Foreign key check failed after items migration: {violations[:5]}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _items_create_table_sql(schema_sql: str, table_name: str) -> str:
    start_marker = "CREATE TABLE IF NOT EXISTS items ("
    next_marker = "\n\nCREATE INDEX IF NOT EXISTS idx_items_normalized_name"
    start = schema_sql.index(start_marker)
    end = schema_sql.index(next_marker, start)
    create_sql = schema_sql[start:end].strip()
    return create_sql.replace("CREATE TABLE IF NOT EXISTS items", f"CREATE TABLE {table_name}", 1)


def _table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
