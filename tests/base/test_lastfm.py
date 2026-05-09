import unittest
from unittest.mock import patch

from supysonic.lastfm import LastFm


class LastFmTestCase(unittest.TestCase):
    def test_blank_credentials_disable_linking(self):
        user = FakeUser()

        with patch("supysonic.lastfm.requests.get") as get:
            status, error = LastFm({"api_key": "", "secret": ""}, user).link_account(
                "token"
            )

        self.assertFalse(status)
        self.assertEqual(error, "No API key set")
        get.assert_not_called()


class FakeUser:
    lastfm_session = None
    lastfm_status = False

    def save(self):
        pass


if __name__ == "__main__":
    unittest.main()
