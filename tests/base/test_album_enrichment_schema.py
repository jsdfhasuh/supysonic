import unittest
from pathlib import Path

from supysonic import db

from ..testbase import TestBase, TestConfig


class AlbumEnrichmentSchemaTestCase(TestBase):
    def test_album_enrichment_columns_exist(self):
        columns = {
            row[1]
            for row in db.db.execute_sql("PRAGMA table_info(album)").fetchall()
        }

        self.assertIn("release_date", columns)
        self.assertIn("release_type", columns)
        self.assertIn("album_info_json", columns)

    def test_album_enrichment_config_defaults_exist(self):
        config = TestConfig(with_webui=False, with_api=False)

        self.assertIn("api_url", config.MUSICBRAINZ)
        self.assertIn("user_agent", config.MUSICBRAINZ)
        self.assertFalse(config.DISCOGS["enabled"])
        self.assertEqual(config.DISCOGS["token"], "")

    def test_packaged_sqlite_schema_contains_album_enrichment_columns(self):
        schema_path = (
            Path(__file__).resolve().parents[2]
            / "supysonic"
            / "schema"
            / "sqlite.sql"
        )

        schema = schema_path.read_text(encoding="utf-8")

        self.assertIn("release_date", schema)
        self.assertIn("release_type", schema)
        self.assertIn("album_info_json", schema)


if __name__ == "__main__":
    unittest.main()
