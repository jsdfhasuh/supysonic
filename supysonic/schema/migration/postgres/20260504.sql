UPDATE review_task
SET expires_at = created + INTERVAL '3 days'
WHERE entity_type = 'album'
  AND status = 'pending'
  AND reason = 'new_album'
  AND expires_at IS NULL;
