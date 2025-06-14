ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096) NULL;
UPDATE meta SET value = '20250524' WHERE `key` = 'schema_version';