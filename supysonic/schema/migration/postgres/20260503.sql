CREATE TABLE IF NOT EXISTS review_task (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(32) NOT NULL,
    entity_id UUID NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason VARCHAR(64) NOT NULL,
    pending_key VARCHAR(96),
    snapshot_json TEXT,
    created TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS album_review_task (
    id UUID PRIMARY KEY,
    album_id UUID NOT NULL REFERENCES album,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason VARCHAR(64) NOT NULL,
    pending_key VARCHAR(96),
    snapshot_json TEXT,
    created TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP
);

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

DROP TABLE IF EXISTS album_review_task;

CREATE INDEX IF NOT EXISTS index_review_task_entity_status ON review_task(entity_type, entity_id, status);
CREATE INDEX IF NOT EXISTS index_review_task_status_created ON review_task(status, created);
CREATE UNIQUE INDEX IF NOT EXISTS index_review_task_pending_key ON review_task(pending_key);
