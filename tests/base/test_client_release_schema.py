import unittest
from pathlib import Path

from supysonic import db

from ..testbase import TestBase


class ClientReleaseSchemaTestCase(TestBase):
    def test_sqlite_client_release_migration_creates_release_table(self):
        migrationPath = (
            Path(__file__).resolve().parents[2]
            / "supysonic"
            / "schema"
            / "migration"
            / "sqlite"
            / "20260507.sql"
        )

        db.db.execute_sql("DROP TABLE IF EXISTS client_release")
        for statement in migrationPath.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                db.db.execute_sql(statement)

        columns = {row[1] for row in db.db.execute_sql("PRAGMA table_info(client_release)").fetchall()}
        self.assertIn("platform", columns)
        self.assertIn("build_name", columns)
        self.assertIn("build_number", columns)
        self.assertIn("download_url", columns)
        self.assertIn("sha256", columns)

    def test_packaged_sqlite_schema_contains_client_release_table(self):
        schemaPath = Path(__file__).resolve().parents[2] / "supysonic" / "schema" / "sqlite.sql"

        schema = schemaPath.read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS client_release", schema)
        self.assertIn("index_client_release_platform_version", schema)


if __name__ == "__main__":
    unittest.main()
