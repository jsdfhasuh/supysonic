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


if __name__ == "__main__":
    unittest.main()
