ALTER TABLE album_review_task ADD COLUMN pending_key VARCHAR(96) NULL;
CREATE UNIQUE INDEX index_album_review_task_pending_key ON album_review_task(pending_key);
