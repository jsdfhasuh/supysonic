CREATE TABLE IF NOT EXISTS shared_track_link (
    id CHAR(32) PRIMARY KEY,
    token VARCHAR(96) NOT NULL UNIQUE,
    track_id CHAR(32) NOT NULL REFERENCES track(id),
    created_by_id CHAR(32) NOT NULL REFERENCES user(id),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
