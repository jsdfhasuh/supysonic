from typing import Iterable, List, Set

from .db import UserRecommendationFeedback, now

HOT_RECOMMENDED_SCOPE = "hot_recommended"
RECOMMENDATION_FEEDBACK_ACTION_DISLIKE = "dislike"
RECOMMENDATION_FEEDBACK_ACTION_RESTORE = "restore"
VALID_RECOMMENDATION_FEEDBACK_ACTIONS = {
    RECOMMENDATION_FEEDBACK_ACTION_DISLIKE,
    RECOMMENDATION_FEEDBACK_ACTION_RESTORE,
}


def set_recommendation_feedback(
    user,
    song_id: str,
    action: str,
    scope: str = HOT_RECOMMENDED_SCOPE,
    reason: str = "user_dislike",
    source: str = "api",
) -> UserRecommendationFeedback:
    song_id = str(song_id or "").strip()
    action = str(action or "").strip().lower()
    scope = str(scope or "").strip() or HOT_RECOMMENDED_SCOPE
    reason = str(reason or "").strip() or "user_dislike"
    source = str(source or "").strip() or "api"

    if not song_id:
        raise ValueError("recommendation feedback id is required")
    if len(song_id) > 96:
        raise ValueError("recommendation feedback id is too long")
    if action not in VALID_RECOMMENDATION_FEEDBACK_ACTIONS:
        raise ValueError("invalid recommendation feedback action")
    if scope != HOT_RECOMMENDED_SCOPE:
        raise ValueError("invalid recommendation feedback scope")
    if len(reason) > 64:
        raise ValueError("recommendation feedback reason is too long")
    if len(source) > 64:
        raise ValueError("recommendation feedback source is too long")

    current_time = now()
    feedback, _ = UserRecommendationFeedback.get_or_create(
        user=user,
        song_id=song_id,
        scope=scope,
        defaults={
            "action": action,
            "reason": reason,
            "source": source,
            "created_at": current_time,
            "updated_at": current_time,
            "deleted_at": None
            if action == RECOMMENDATION_FEEDBACK_ACTION_DISLIKE
            else current_time,
        },
    )
    feedback.action = action
    feedback.reason = reason
    feedback.source = source
    feedback.updated_at = current_time
    feedback.deleted_at = (
        None if action == RECOMMENDATION_FEEDBACK_ACTION_DISLIKE else current_time
    )
    feedback.save()
    return feedback


def get_disliked_recommended_song_ids(
    user,
    scope: str = HOT_RECOMMENDED_SCOPE,
) -> Set[str]:
    if user is None:
        return set()
    return {
        feedback.song_id
        for feedback in UserRecommendationFeedback.select(
            UserRecommendationFeedback.song_id
        ).where(
            UserRecommendationFeedback.user == user,
            UserRecommendationFeedback.scope == scope,
            UserRecommendationFeedback.action == RECOMMENDATION_FEEDBACK_ACTION_DISLIKE,
            UserRecommendationFeedback.deleted_at.is_null(True),
        )
    }


def filter_disliked_recommended_tracks(
    user,
    tracks: Iterable[object],
    scope: str = HOT_RECOMMENDED_SCOPE,
) -> List[object]:
    disliked_song_ids = get_disliked_recommended_song_ids(user, scope=scope)
    if not disliked_song_ids:
        return list(tracks)
    return [track for track in tracks if str(track.id) not in disliked_song_ids]
