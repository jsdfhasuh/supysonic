CREATE TABLE IF NOT EXISTS album_review_task (
    id CHAR(36) PRIMARY KEY,
    album_id CHAR(36) NOT NULL REFERENCES album(id) ON DELETE CASCADE,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason VARCHAR(64) NOT NULL,
    snapshot_json TEXT,
    created DATETIME NOT NULL,
    updated DATETIME NOT NULL,
    resolved_at DATETIME
);

CREATE INDEX IF NOT EXISTS index_album_review_task_album_status ON album_review_task(album_id, status);
CREATE INDEX IF NOT EXISTS index_album_review_task_status_created ON album_review_task(status, created);
