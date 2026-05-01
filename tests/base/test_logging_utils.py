import unittest

from supysonic.logging_utils import format_log_event


class LoggingUtilsTestCase(unittest.TestCase):
    def test_formats_basic_event(self):
        self.assertEqual(
            format_log_event("api", "auth_failure", user="alice", reason="wrong_password"),
            "api event=auth_failure user=alice reason=wrong_password",
        )

    def test_redacts_sensitive_fields(self):
        line = format_log_event("api", "auth_failure", p="secret", t="token", s="salt")

        self.assertIn("p=***", line)
        self.assertIn("t=***", line)
        self.assertIn("s=***", line)
        self.assertNotIn("secret", line)
        self.assertNotIn("token", line)
        self.assertNotIn("salt", line)

    def test_escapes_newline(self):
        line = format_log_event("api", "bad_request", reason="bad\nthing")

        self.assertNotIn("\nbad", line)
        self.assertIn('reason="bad\\nthing"', line)

    def test_formats_list_as_comma_joined(self):
        line = format_log_event("emo", "device_register", roles=["player", "controller"])

        self.assertIn("roles=player,controller", line)

    def test_quotes_query_strings_with_reserved_characters(self):
        line = format_log_event("access", "request", query="u=root&t=abc&s=def")

        self.assertIn('query="u=root&t=abc&s=def"', line)
