import uuid
from typing import List, Optional

from flask import Response, flash, redirect, render_template, request, url_for

from ..db import MusicRequest, User
from . import frontend


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip()


def _parse_track_titles(value: Optional[str]) -> List[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").casefold().split())


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


def _get_music_request(uid: str) -> Optional[MusicRequest]:
    try:
        request_id = uuid.UUID(uid)
    except ValueError:
        return None
    return MusicRequest.get_or_none(MusicRequest.id == request_id)


@frontend.route("/music-requests")
def music_request_index() -> str:
    status_filter = request.args.get("status")
    if status_filter not in MusicRequest.STATUSES:
        status_filter = None

    query = (
        MusicRequest.select(MusicRequest, User)
        .join(User)
        .order_by(
            (MusicRequest.status == MusicRequest.STATUS_PENDING).desc(),
            MusicRequest.created_at.desc(),
        )
    )
    if status_filter:
        query = query.where(MusicRequest.status == status_filter)

    counts = {
        status: MusicRequest.select()
        .where(MusicRequest.status == status)
        .count()
        for status in MusicRequest.STATUSES
    }

    return render_template(
        "music_requests.html",
        requests=list(query),
        counts=counts,
        status_filter=status_filter,
        statuses=MusicRequest.STATUSES,
    )


@frontend.route("/music-requests", methods=["POST"])
def music_request_create() -> Response:
    artist_name = _clean_text(request.form.get("artist_name"))
    album_name = _clean_text(request.form.get("album_name"))
    note = _clean_text(request.form.get("note"))
    track_titles = _parse_track_titles(request.form.get("tracks"))

    if not artist_name:
        flash("Missing artist name", "danger")
        return redirect(url_for("frontend.music_request_index"))
    if len(artist_name) > 256 or len(album_name) > 256:
        flash("Artist and album names must be 256 characters or less", "danger")
        return redirect(url_for("frontend.music_request_index"))
    if not album_name and not track_titles:
        flash("Provide an album name or at least one track title", "danger")
        return redirect(url_for("frontend.music_request_index"))

    record = MusicRequest.create(
        user=request.user,
        artist_name=artist_name,
        album_name=album_name or None,
        note=note or None,
    )
    record.set_track_titles(track_titles)
    record.save()

    if _has_similar_pending_request(record):
        flash("Music request saved. A similar pending request already exists.", "warning")
    else:
        flash("Music request saved.", "success")
    return redirect(url_for("frontend.music_request_index"))


@frontend.route("/music-requests/<uid>/delete", methods=["POST"])
def music_request_delete(uid: str) -> Response:
    record = _get_music_request(uid)
    if record is None:
        flash("Unknown music request", "warning")
        return redirect(url_for("frontend.music_request_index"))
    if record.user != request.user and not request.user.admin:
        flash("You are not allowed to delete this music request", "danger")
        return redirect(url_for("frontend.music_request_index"))

    record.delete_instance()
    flash("Music request deleted.", "success")
    return redirect(url_for("frontend.music_request_index"))


@frontend.route("/music-requests/<uid>/status", methods=["POST"])
def music_request_update_status(uid: str) -> Response:
    record = _get_music_request(uid)
    if record is None:
        flash("Unknown music request", "warning")
        return redirect(url_for("frontend.music_request_index"))
    if not request.user.admin:
        flash("You are not allowed to update music request status", "danger")
        return redirect(url_for("frontend.music_request_index"))

    status = request.form.get("status")
    if status not in MusicRequest.STATUSES:
        flash("Invalid music request status", "danger")
        return redirect(url_for("frontend.music_request_index"))

    status_note = _clean_text(request.form.get("status_note"))
    record.status = status
    record.status_note = status_note or None
    record.save()
    flash("Music request status updated.", "success")
    return redirect(url_for("frontend.music_request_index"))
