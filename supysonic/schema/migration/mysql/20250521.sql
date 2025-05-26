
CREATE TABLE track_artist (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    track_id CHAR(32) NOT NULL,
    artist_id CHAR(32) NOT NULL,
    artist VARCHAR(255) NOT NULL,  
    position INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (track_id) REFERENCES track(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artist(id) ON DELETE CASCADE,
    UNIQUE KEY(track_id, artist_id)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX index_track_artist_track_id_fk ON track_artist(track_id);
CREATE INDEX index_track_artist_artist_id_fk ON track_artist(artist_id);

CREATE TABLE album_artist (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    album_id CHAR(32) NOT NULL,
    artist_id CHAR(32) NOT NULL,
    album VARCHAR(255) NOT NULL,  
    artist VARCHAR(255) NOT NULL,  
    position INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (album_id) REFERENCES album(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artist(id) ON DELETE CASCADE,
    UNIQUE KEY(album_id, artist_id)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;




