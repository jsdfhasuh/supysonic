import importlib
import unittest


class DbLayerContractTestCase(unittest.TestCase):
    def test_db_facade_exports_existing_public_names(self):
        db_module = importlib.import_module("supysonic.db")
        expected_names = [
            "SCHEMA_VERSION",
            "db",
            "now",
            "random",
            "PrimaryKeyField",
            "Meta",
            "PathMixin",
            "Image",
            "Folder",
            "Artist",
            "Album",
            "ReviewTask",
            "AlbumReviewTask",
            "AlbumArtist",
            "Track",
            "TrackArtist",
            "User",
            "User_Play_Activity",
            "ClientPrefs",
            "EmoSessionQueue",
            "EmoLocalQueue",
            "EmoPlaybackState",
            "StarredFolder",
            "StarredArtist",
            "StarredAlbum",
            "StarredTrack",
            "RatingFolder",
            "RatingTrack",
            "ChatMessage",
            "Playlist",
            "SharedTrackLink",
            "RadioStation",
            "ClientRelease",
            "execute_sql_resource_script",
            "init_database",
            "release_database",
            "open_connection",
            "close_connection",
        ]

        for name in expected_names:
            with self.subTest(name=name):
                self.assertTrue(hasattr(db_module, name))

    def test_db_layer_package_exists(self):
        package = importlib.import_module("supysonic.db_layer")

        self.assertIsNotNone(package)

    def test_core_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        core = importlib.import_module("supysonic.db_layer.core")

        self.assertIs(db_module.db, core.db)
        self.assertIs(db_module.Meta, core.Meta)
        self.assertIs(db_module.PathMixin, core.PathMixin)
        self.assertIs(db_module.now, core.now)
        self.assertIs(db_module.random, core.random)
        self.assertIs(db_module.PrimaryKeyField, core.PrimaryKeyField)

    def test_schema_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        schema = importlib.import_module("supysonic.db_layer.schema")

        self.assertEqual(db_module.SCHEMA_VERSION, schema.SCHEMA_VERSION)
        self.assertIs(db_module.execute_sql_resource_script, schema.execute_sql_resource_script)


if __name__ == "__main__":
    unittest.main()
