CREATE TABLE image (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    path VARCHAR(4096) NOT NULL,
    image_type VARCHAR(10) NOT NULL,
    related_id VARCHAR(36) NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

UPDATE meta SET value = '20250523' WHERE `key` = 'schema_version';