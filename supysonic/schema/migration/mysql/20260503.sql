CREATE TABLE IF NOT EXISTS review_task (
    id CHAR(32) PRIMARY KEY,
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
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS album_review_task (
    id CHAR(32) PRIMARY KEY,
    album_id CHAR(32) NOT NULL REFERENCES album(id),
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason VARCHAR(64) NOT NULL,
    pending_key VARCHAR(96),
    snapshot_json TEXT,
    created DATETIME NOT NULL,
    updated DATETIME NOT NULL,
    resolved_at DATETIME
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

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
    pending_key,
    snapshot_json,
    created,
    updated,
    resolved_at,
    NULL
FROM album_review_task;

DROP TABLE album_review_task;

CREATE INDEX index_review_task_entity_status ON review_task(entity_type, entity_id, status);
CREATE INDEX index_review_task_status_created ON review_task(status, created);
CREATE UNIQUE INDEX index_review_task_pending_key ON review_task(pending_key);
