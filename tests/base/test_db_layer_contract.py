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

    def test_runtime_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        runtime = importlib.import_module("supysonic.db_layer.runtime")

        self.assertIs(db_module.init_database, runtime.init_database)
        self.assertIs(db_module.release_database, runtime.release_database)
        self.assertIs(db_module.open_connection, runtime.open_connection)
        self.assertIs(db_module.close_connection, runtime.close_connection)

    def test_serializer_module_exists(self):
        serializers = importlib.import_module("supysonic.db_layer.serializers")

        for name in (
            "serialize_folder_child",
            "serialize_folder_artist",
            "serialize_folder_directory",
            "serialize_artist",
            "serialize_album",
            "serialize_track_child",
            "serialize_user",
            "serialize_chat_message",
            "serialize_playlist",
            "serialize_radio_station",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(serializers, name))


if __name__ == "__main__":
    unittest.main()
