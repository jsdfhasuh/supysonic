import sqlite3


def _table_exists(connection, table):
    cursor = connection.cursor()
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(connection, table, column):
    cursor = connection.cursor()
    rows = cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in rows)


def _create_review_task_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS review_task (
            id CHAR(36) PRIMARY KEY,
            entity_type VARCHAR(32) NOT NULL,
            entity_id CHAR(36) NOT NULL,
            task_type VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            reason VARCHAR(64) NOT NULL,
            pending_key VARCHAR(96),
            snapshot_json TEXT,
            created DATETIME NOT NULL,
            updated DATETIME NOT NULL,
            resolved_at DATETIME,
            expires_at DATETIME
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS index_review_task_entity_status ON review_task(entity_type, entity_id, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS index_review_task_status_created ON review_task(status, created)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS index_review_task_pending_key ON review_task(pending_key)"
    )


def apply(args):
    database_file = args.pop("database")
    with sqlite3.connect(database_file, **args) as connection:
        cursor = connection.cursor()

        if _table_exists(connection, "album_review_task") and not _table_exists(connection, "review_task"):
            _create_review_task_table(cursor)
            has_pending_key = _column_exists(connection, "album_review_task", "pending_key")
            pending_key_column = "pending_key" if has_pending_key else "NULL"
            cursor.execute(
                f"""
                INSERT INTO review_task (
                    id,
                    entity_type,
                    entity_id,
                    task_type,
                    status,
                    reason,
                    pending_key,
                    snapshot_json,
                    created,
                    updated,
                    resolved_at,
                    expires_at
                )
                SELECT
                    id,
                    'album',
                    album_id,
                    task_type,
                    status,
                    reason,
                    {pending_key_column},
                    snapshot_json,
                    created,
                    updated,
                    resolved_at,
                    NULL
                FROM album_review_task
                """
            )
            cursor.execute("DROP TABLE album_review_task")
        else:
            _create_review_task_table(cursor)

        connection.commit()
