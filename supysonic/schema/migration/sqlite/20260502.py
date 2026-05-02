import sqlite3


def _column_exists(connection, table, column):
    cursor = connection.cursor()
    rows = cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in rows)


def _table_exists(connection, table):
    cursor = connection.cursor()
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def apply(args):
    databaseFile = args.pop("database")
    with sqlite3.connect(databaseFile, **args) as connection:
        cursor = connection.cursor()

        if not _column_exists(connection, "artist", "artist_info_json"):
            cursor.execute("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")

        if not _column_exists(connection, "artist", "real_artist_id"):
            cursor.execute(
                "ALTER TABLE artist ADD COLUMN real_artist_id CHAR(36) REFERENCES artist(id)"
            )

        if not _column_exists(connection, "album", "year"):
            cursor.execute("ALTER TABLE album ADD COLUMN year VARCHAR(255)")

        if not _table_exists(connection, "user_play_activity"):
            cursor.execute(
                """
                CREATE TABLE user_play_activity (
                    id CHAR(36) PRIMARY KEY,
                    track_id CHAR(36) NOT NULL REFERENCES track(id) ON DELETE CASCADE,
                    user_id CHAR(36) NOT NULL REFERENCES user(id) ON DELETE CASCADE,
                    time DATETIME NOT NULL
                )
                """
            )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS index_activity_user_id_fk ON user_play_activity(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS index_activity_track_id_fk ON user_play_activity(track_id)"
        )
        connection.commit()
