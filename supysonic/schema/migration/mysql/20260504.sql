UPDATE review_task
SET expires_at = DATE_ADD(created, INTERVAL 3 DAY)
WHERE entity_type = 'album'
  AND status = 'pending'
  AND reason = 'new_album'
  AND expires_at IS NULL;
