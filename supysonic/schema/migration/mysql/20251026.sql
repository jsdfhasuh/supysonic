ALTER TABLE artist
    ADD COLUMN real_artist_id CHAR(36) NULL;

ALTER TABLE artist
    ADD CONSTRAINT fk_artist_real_artist
    FOREIGN KEY (real_artist_id) REFERENCES artist(id)
    ON DELETE SET NULL;