import unittest
from pathlib import Path

from supysonic import db
from supysonic.recommendation_feedback import (
    HOT_RECOMMENDED_SCOPE,
    get_disliked_recommended_song_ids,
    set_recommendation_feedback,
)

from ..testbase import TestBase


class RecommendationFeedbackTestCase(TestBase):
    def test_feedback_table_exists_in_packaged_schema(self):
        columns = {
            row[1]
            for row in db.db.execute_sql(
                "PRAGMA table_info(user_recommendation_feedback)"
            ).fetchall()
        }

        self.assertIn("user_id", columns)
        self.assertIn("song_id", columns)
        self.assertIn("scope", columns)
        self.assertIn("deleted_at", columns)

    def test_sqlite_feedback_migration_creates_table(self):
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "supysonic"
            / "schema"
            / "migration"
            / "sqlite"
            / "20260524.sql"
        )

        db.db.execute_sql("DROP TABLE IF EXISTS user_recommendation_feedback")
        for statement in migration_path.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                db.db.execute_sql(statement)

        columns = {
            row[1]
            for row in db.db.execute_sql(
                "PRAGMA table_info(user_recommendation_feedback)"
            ).fetchall()
        }
        self.assertIn("song_id", columns)
        self.assertIn("deleted_at", columns)

    def test_dislike_and_restore_are_idempotent(self):
        user = db.User.get(db.User.name == "alice")
        song_id = "song-123"

        set_recommendation_feedback(user, song_id, "dislike")
        set_recommendation_feedback(user, song_id, "dislike")

        self.assertEqual(db.UserRecommendationFeedback.select().count(), 1)
        self.assertEqual(
            get_disliked_recommended_song_ids(user, HOT_RECOMMENDED_SCOPE),
            {song_id},
        )

        set_recommendation_feedback(user, song_id, "restore")
        set_recommendation_feedback(user, song_id, "restore")

        feedback = db.UserRecommendationFeedback.get()
        self.assertEqual(db.UserRecommendationFeedback.select().count(), 1)
        self.assertEqual(feedback.action, "restore")
        self.assertIsNotNone(feedback.deleted_at)
        self.assertEqual(
            get_disliked_recommended_song_ids(user, HOT_RECOMMENDED_SCOPE),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
