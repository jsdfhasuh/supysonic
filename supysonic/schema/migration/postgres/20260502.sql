ALTER TABLE artist ADD COLUMN IF NOT EXISTS artist_info_json VARCHAR(4096);
ALTER TABLE artist ADD COLUMN IF NOT EXISTS real_artist_id UUID REFERENCES artist(id);
ALTER TABLE album ADD COLUMN IF NOT EXISTS year VARCHAR(255);

CREATE TABLE IF NOT EXISTS user_play_activity (
    id UUID PRIMARY KEY,
    track_id UUID NOT NULL REFERENCES track(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    time TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS index_activity_user_id_fk ON user_play_activity(user_id);
CREATE INDEX IF NOT EXISTS index_activity_track_id_fk ON user_play_activity(track_id);
