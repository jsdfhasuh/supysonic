CREATE TABLE IF NOT EXISTS emo_session_queue (
    id UUID PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL UNIQUE,
    user_name VARCHAR(64) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    queue_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS emo_playback_state (
    id UUID PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL UNIQUE,
    user_name VARCHAR(64) NOT NULL,
    owner_client_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL,
    track_id VARCHAR(128),
    position_ms INTEGER NOT NULL DEFAULT 0,
    volume INTEGER,
    playback_json TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
