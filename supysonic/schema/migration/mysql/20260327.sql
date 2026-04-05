CREATE TABLE IF NOT EXISTS emo_local_queue (
    id CHAR(32) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    queue_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    position_ms INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uniq_emo_local_queue_session_client (session_id, owner_client_id)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE emo_playback_state_new (
    id CHAR(32) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    user_name VARCHAR(64) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL,
    track_id VARCHAR(128),
    position_ms INTEGER NOT NULL DEFAULT 0,
    volume INTEGER,
    playback_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uniq_emo_playback_state_session_client (session_id, owner_client_id)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT INTO emo_playback_state_new (
    id, session_id, user_name, owner_client_id, state, track_id, position_ms, volume, playback_json, created_at, updated_at
)
SELECT
    id, session_id, user_name, owner_client_id, state, track_id, position_ms, volume, playback_json, created_at, updated_at
FROM emo_playback_state;

DROP TABLE emo_playback_state;
RENAME TABLE emo_playback_state_new TO emo_playback_state;
