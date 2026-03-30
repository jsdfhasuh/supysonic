CREATE TABLE IF NOT EXISTS emo_session_queue (
    id CHAR(32) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL UNIQUE,
    user_name VARCHAR(64) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    queue_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emo_playback_state (
    id CHAR(32) PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL UNIQUE,
    user_name VARCHAR(64) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL,
    track_id VARCHAR(128),
    position_ms INTEGER NOT NULL DEFAULT 0,
    volume INTEGER,
    playback_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
