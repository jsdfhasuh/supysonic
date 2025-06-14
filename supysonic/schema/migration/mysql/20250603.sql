ALTER TABLE album ADD COLUMN year VARCHAR(255) NULL;
UPDATE meta SET value = '20250603' WHERE `key` = 'schema_version';