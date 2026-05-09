CREATE TABLE IF NOT EXISTS client_release (
    id CHAR(36) PRIMARY KEY,
    platform VARCHAR(16) NOT NULL,
    file_type VARCHAR(16) NOT NULL,
    build_name VARCHAR(64) NOT NULL,
    build_number INTEGER NOT NULL,
    version VARCHAR(80) NOT NULL,
    publish_mode VARCHAR(16) NOT NULL,
    file_name VARCHAR(256),
    file_path VARCHAR(4096),
    download_url VARCHAR(2048),
    file_size INTEGER,
    sha256 CHAR(64),
    release_notes TEXT,
    active BOOLEAN NOT NULL DEFAULT 1,
    created DATETIME NOT NULL,
    updated DATETIME NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS index_client_release_platform_version ON client_release(platform, build_name, build_number);
CREATE INDEX IF NOT EXISTS index_client_release_platform_active ON client_release(platform, active);
