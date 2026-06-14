import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from flask import Response, request

from ..db import MusicRequest, User, db
from . import api_routing
from .exceptions import Forbidden, GenericError, MissingParameter, NotFound


MAX_COUNT = 500
DEFAULT_COUNT = 50
DEFAULT_OFFSET = 0


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip()


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").casefold().split())


def _parse_track_titles(
    track_values: Iterable[str], tracks_value: Optional[str]
) -> List[str]:
    tracks = [track.strip() for track in track_values if track.strip()]
    tracks.extend(
        line.strip() for line in (tracks_value or "").splitlines() if line.strip()
    )
    return tracks


def _parse_non_negative_int(name: str, default: int) -> int:
    raw_value = request.values.get(name)
    if raw_value is None or raw_value == "":
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise GenericError(f"Invalid {name}") from exc
    if value < 0:
        raise GenericError(f"Invalid {name}")
    return value


def _get_music_request() -> MusicRequest:
    raw_id = request.values.get("id")
    if not raw_id:
        raise MissingParameter("id")
    try:
        request_id = uuid.UUID(raw_id)
    except ValueError as exc:
        raise GenericError("Invalid music request id") from exc

    record = MusicRequest.get_or_none(MusicRequest.id == request_id)
    if record is None:
        raise NotFound("MusicRequest")
    return record


def _has_similar_pending_request(record: MusicRequest) -> bool:
    if not record.album_name:
        return False

    target_artist = _normalize(record.artist_name)
    target_album = _normalize(record.album_name)
    query = MusicRequest.select().where(
        MusicRequest.status == MusicRequest.STATUS_PENDING,
        MusicRequest.id != record.id,
    )
    for candidate in query:
        if (
            _normalize(candidate.artist_name) == target_artist
            and _normalize(candidate.album_name) == target_album
        ):
            return True
    return False


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def _serialize_music_request(
    record: MusicRequest,
    *,
    similar_pending: Optional[bool] = None,
) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "id": str(record.id),
        "artistName": record.artist_name,
        "status": record.status,
        "createdAt": _datetime_to_text(record.created_at),
        "updatedAt": _datetime_to_text(record.updated_at),
        "userId": str(record.user.id),
        "username": record.user.name,
        "canDelete": request.user.admin or record.user.id == request.user.id,
        "canUpdateStatus": request.user.admin,
    }

    if record.album_name:
        info["albumName"] = record.album_name
    track_titles = record.get_track_titles()
    if track_titles:
        info["track"] = track_titles
    if record.note:
        info["note"] = record.note
    if record.status_note:
        info["statusNote"] = record.status_note
    if record.resolved_at:
        info["resolvedAt"] = _datetime_to_text(record.resolved_at)
    if similar_pending is not None:
        info["similarPending"] = similar_pending
    return info


@api_routing("/getMusicRequests")
def get_music_requests() -> Response:
    status = request.values.get("status")
    if status and status not in MusicRequest.STATUSES:
        raise GenericError("Invalid music request status")

    count = min(_parse_non_negative_int("count", DEFAULT_COUNT), MAX_COUNT)
    offset = _parse_non_negative_int("offset", DEFAULT_OFFSET)

    query = (
        MusicRequest.select(MusicRequest, User)
        .join(User)
        .order_by(
            (MusicRequest.status == MusicRequest.STATUS_PENDING).desc(),
            MusicRequest.created_at.desc(),
        )
    )
    if status:
        query = query.where(MusicRequest.status == status)

    total = query.count()
    records = [
        _serialize_music_request(record)
        for record in query.limit(count).offset(offset)
    ]
    payload = {
        "count": len(records),
        "offset": offset,
        "total": total,
        "pendingCount": MusicRequest.select()
        .where(MusicRequest.status == MusicRequest.STATUS_PENDING)
        .count(),
        "resolvedCount": MusicRequest.select()
        .where(MusicRequest.status == MusicRequest.STATUS_RESOLVED)
        .count(),
        "rejectedCount": MusicRequest.select()
        .where(MusicRequest.status == MusicRequest.STATUS_REJECTED)
        .count(),
        "musicRequest": records,
    }
    return request.formatter("musicRequests", payload)


@api_routing("/createMusicRequest")
@db.atomic()
def create_music_request() -> Response:
    artist_name = _clean_text(request.values.get("artistName"))
    album_name = _clean_text(request.values.get("albumName"))
    note = _clean_text(request.values.get("note"))
    track_titles = _parse_track_titles(
        request.values.getlist("track"),
        request.values.get("tracks"),
    )

    if not artist_name:
        raise MissingParameter("artistName")
    if len(artist_name) > 256 or len(album_name) > 256:
        raise GenericError("Artist and album names must be 256 characters or less")
    if not album_name and not track_titles:
        raise GenericError("Provide an album name or at least one track title")

    record = MusicRequest.create(
        user=request.user,
        artist_name=artist_name,
        album_name=album_name or None,
        note=note or None,
    )
    record.set_track_titles(track_titles)
    record.save()
    similar_pending = _has_similar_pending_request(record)
    return request.formatter(
        "musicRequest",
        _serialize_music_request(record, similar_pending=similar_pending),
    )


@api_routing("/deleteMusicRequest")
def delete_music_request() -> Response:
    record = _get_music_request()
    if record.user != request.user and not request.user.admin:
        raise Forbidden()

    record.delete_instance()
    return request.formatter.empty


@api_routing("/updateMusicRequestStatus")
def update_music_request_status() -> Response:
    record = _get_music_request()
    if not request.user.admin:
        raise Forbidden()

    status = request.values.get("status")
    if not status:
        raise MissingParameter("status")
    if status not in MusicRequest.STATUSES:
        raise GenericError("Invalid music request status")

    status_note = _clean_text(request.values.get("statusNote"))
    record.status = status
    record.status_note = status_note or None
    record.save()
    return request.formatter("musicRequest", _serialize_music_request(record))
