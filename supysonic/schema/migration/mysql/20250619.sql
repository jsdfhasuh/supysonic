CREATE TABLE user_play_activity (
    id CHAR(32) PRIMARY KEY,
    track_id CHAR(32) NOT NULL,
    user_id CHAR(32) NOT NULL, 
    time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_track FOREIGN KEY (track_id) REFERENCES track(id) ON DELETE CASCADE,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX index_activity_user_id_fk ON user_play_activity(user_id);
CREATE INDEX index_activity_track_id_fk ON user_play_activity(track_id);