import uuid

from ..db import AlbumArtist, AlbumReviewTask, TrackArtist, now


def listMetadataReviewTasks(status=None):
    query = AlbumReviewTask.select().order_by(AlbumReviewTask.created.desc())
    if status:
        query = query.where(AlbumReviewTask.status == status)
    return query


def getMetadataReviewTask(taskId):
    try:
        task_uuid = uuid.UUID(str(taskId))
    except ValueError as exc:
        raise ValueError("Invalid review task id") from exc

    task = AlbumReviewTask.get_or_none(AlbumReviewTask.id == task_uuid)
    if task is None:
        raise LookupError("Review task not found")
    return task


def _resolveMetadataReviewTask(task, nextStatus):
    if task.status != "pending":
        raise ValueError("Only pending review tasks can be updated")

    task.status = nextStatus
    task.updated = now()
    task.resolved_at = task.updated
    task.save()
    return task


def confirmMetadataReviewTask(task):
    return _resolveMetadataReviewTask(task, "confirmed")


def dismissMetadataReviewTask(task):
    return _resolveMetadataReviewTask(task, "dismissed")


def getTaskRelatedArtists(task):
    artists = []
    seen_artist_ids = set()
    track_rows = list(task.album.tracks)
    related_album_artists = [relation.artist_id for relation in task.album.album_artists.order_by(AlbumArtist.position, AlbumArtist.id)]
    related_track_artists = []
    for track in track_rows:
        related_track_artists.extend(
            relation.artist_id for relation in track.track_artists.order_by(TrackArtist.position, TrackArtist.id)
        )

    for artist in [task.album.artist] + [track.artist for track in track_rows] + related_album_artists + related_track_artists:
        if artist.id in seen_artist_ids:
            continue
        seen_artist_ids.add(artist.id)
        artists.append(artist)
    return artists
