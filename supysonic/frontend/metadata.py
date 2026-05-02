import logging
import json

from flask import flash, g, redirect, render_template, request, session, url_for
from flask import current_app
from functools import wraps
from peewee import fn

from ..db import AlbumArtist, ClientPrefs, User, Artist, Album, Track, TrackArtist, db
from ..lastfm import LastFm
from ..listenbrainz import ListenBrainz
from ..logging_utils import format_log_event
from ..managers.user import UserManager
from .metadata_actions import assignPrimaryArtist, resolvePrimaryArtist, updateArtistMetadata
from .metadata_review import (
    confirmMetadataReviewTask,
    dismissMetadataReviewTask,
    getMetadataReviewTask,
    getTaskRelatedArtists,
    listMetadataReviewTasks,
)

from . import admin_only, frontend

logger = logging.getLogger(__name__)


def logMetadataEvent(level, event, **fields):
    user = getattr(getattr(request, "user", None), "name", "-") or "-"
    context = {
        "request_id": getattr(g, "supysonic_request_id", "-"),
        "user": user,
        "path": request.path,
    }
    context.update(fields)
    logger.log(level, format_log_event("metadata", event, **context))


def formatDurationLabel(totalSeconds):
    hours, remainder = divmod(int(totalSeconds or 0), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def syncAlbumArtists(album, previousArtistId=None):
    if previousArtistId and previousArtistId != album.artist_id:
        AlbumArtist.delete().where(
            AlbumArtist.album_id == album,
            AlbumArtist.artist_id == previousArtistId,
        ).execute()

    primary_relation, _ = AlbumArtist.get_or_create(
        album_id=album,
        artist_id=album.artist,
        defaults={"position": 1},
    )
    if primary_relation.position != 1:
        primary_relation.position = 1
        primary_relation.save()


def syncTrackArtists(track, previousArtistId=None):
    if previousArtistId and previousArtistId != track.artist_id:
        TrackArtist.delete().where(
            TrackArtist.track_id == track,
            TrackArtist.artist_id == previousArtistId,
        ).execute()

    primary_relation, _ = TrackArtist.get_or_create(
        track_id=track,
        artist_id=track.artist,
        defaults={"position": 1},
    )
    if primary_relation.position != 1:
        primary_relation.position = 1
        primary_relation.save()


def getReviewSection(defaultSection="album"):
    section = request.args.get("section", defaultSection)
    if section not in ("album", "tracks", "artists"):
        return defaultSection
    return section


def getReviewRedirectResponse(task):
    if request.args.get("redirect") != "1":
        return None
    return redirect(url_for("frontend.metadata_review_task", task_id=task.id, section=getReviewSection()))


def getMetadataCoverArtUrl(entityId):
    return f"/rest/getCoverArt?id={entityId}&v=1.15.0&c=web"


def getReviewArtistImageUrl(artist, artistInfo):
    for key in ("largeImageUrl", "mediumImageUrl", "smallImageUrl"):
        imageUrl = artistInfo.get(key) or ""
        if imageUrl.startswith(("http://", "https://", "/rest/", "/static/")):
            return imageUrl
    return getMetadataCoverArtUrl(f"ar-{artist.id}")


def buildMetadataArtistCardData(artist):
    return {
        "id": str(artist.id),
        "name": artist.name,
        "image": getMetadataCoverArtUrl(f"ar-{artist.id}"),
    }


def ensurePendingReviewTask(task):
    if task.status != "pending":
        raise ValueError("Only pending review tasks can be updated")


def getArtistMetadataRequestData():
    if request.is_json:
        return request.get_json(silent=True) or {}, None

    artistPhoto = request.files.get("artist_photo")
    if artistPhoto and not artistPhoto.filename:
        artistPhoto = None
    return request.form.to_dict(), artistPhoto


@frontend.route("/metadata")
@admin_only
def metadata():
    activeTab = request.args.get("tab", "inbox")
    if activeTab not in ("inbox", "artists", "albums"):
        activeTab = "inbox"

    inbox_tasks = []
    inbox_summary = None
    selected_status = request.args.get("status", "pending")
    if activeTab == "inbox":
        query_status = None if selected_status == "all" else selected_status
        for task in listMetadataReviewTasks(status=query_status):
            snapshot = json.loads(task.snapshot_json or "{}")
            inbox_tasks.append(
                {
                    "id": str(task.id),
                    "album_name": snapshot.get("album_name") or task.album.name,
                    "artist_name": snapshot.get("artist_name") or task.album.artist.get_artist_name(),
                    "year": snapshot.get("year") or task.album.year,
                    "track_count": snapshot.get("track_count", task.album.tracks.count()),
                    "status": task.status,
                    "reason": task.reason,
                    "created": task.created,
                    "cover_art_url": getMetadataCoverArtUrl(f"al-{task.album.id}"),
                }
            )

        inbox_summary = {
            "pending": listMetadataReviewTasks(status="pending").count(),
            "confirmed": listMetadataReviewTasks(status="confirmed").count(),
            "dismissed": listMetadataReviewTasks(status="dismissed").count(),
            "all": listMetadataReviewTasks().count(),
        }

    return render_template(
        "metadata-workspace.html",
        activeTab=activeTab,
        inboxTasks=inbox_tasks,
        inboxSummary=inbox_summary,
        selectedInboxStatus=selected_status,
    )


@frontend.route("/metadata/review-tasks/<task_id>")
@admin_only
def metadata_review_task(task_id):
    try:
        task = getMetadataReviewTask(task_id)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        return {"status": "error", "message": str(exc)}, 404

    album = task.album
    tracks = list(album.tracks.order_by(Track.disc, Track.number, Track.title))
    related_artists = getTaskRelatedArtists(task)
    active_review_tab = getReviewSection()

    review_issues = []
    if not album.year:
        review_issues.append("Missing release year")
    if any(track.artist_id != album.artist_id for track in tracks):
        review_issues.append("Track artist mapping needs review")
    if not review_issues:
        review_issues.append("Metadata review requested for new album")

    review_artist_cards = []
    for artist in related_artists:
        artist_info = artist.get_info()
        review_artist_cards.append(
            {
                "id": str(artist.id),
                "display_name": artist.get_artist_name(),
                "name": artist.name,
                "biography": artist_info.get("biography", ""),
                "image_url": getReviewArtistImageUrl(artist, artist_info),
            }
        )

    review_summary = {
        "status": task.status,
        "created": task.created,
        "track_count": len(tracks),
        "related_artist_count": len(related_artists),
        "total_duration": formatDurationLabel(sum(track.duration for track in tracks)),
        "cover_art_url": getMetadataCoverArtUrl(f"al-{album.id}"),
        "issues": review_issues,
    }

    return render_template(
        "metadata-review-task.html",
        reviewTask=task,
        reviewAlbum=album,
        reviewTracks=tracks,
        reviewArtists=related_artists,
        reviewArtistCards=review_artist_cards,
        reviewSummary=review_summary,
        activeReviewTab=active_review_tab,
        reviewIsEditable=(task.status == "pending"),
    )


@frontend.route("/metadata/artist-suggestions")
@admin_only
def metadata_artist_suggestions():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return {"status": "success", "artists": []}

    normalized_query = query.lower()
    artist_rows = list(
        Artist.select()
        .where(Artist.real_artist.is_null(), fn.Lower(Artist.name).contains(normalized_query))
        .order_by(fn.Lower(Artist.name))
        .limit(20)
    )
    artist_names = sorted(
        [artist.name for artist in artist_rows],
        key=lambda name: (not name.lower().startswith(normalized_query), name.lower()),
    )
    return {"status": "success", "artists": artist_names[:10]}


@frontend.route("/metadata/review-tasks/<task_id>/album", methods=["POST"])
@admin_only
def update_metadata_review_task_album(task_id):
    task = None
    try:
        task = getMetadataReviewTask(task_id)
        ensurePendingReviewTask(task)
    except ValueError as exc:
        logMetadataEvent(logging.WARNING, "review_album_update", result="bad_request", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        logMetadataEvent(logging.WARNING, "review_album_update", result="not_found", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 404
    raw_data = request.get_json(silent=True) or {}
    album = task.album
    previous_artist_id = album.artist_id
    changed_fields = []
    resolved_artist_id = None

    if raw_data.get("name") and raw_data.get("name") != album.name:
        changed_fields.append("name")
    album.name = raw_data.get("name") or album.name
    if raw_data.get("year") and raw_data.get("year") != album.year:
        changed_fields.append("year")
    album.year = raw_data.get("year") or album.year
    artist_name = raw_data.get("artist_name", "").strip()
    if artist_name:
        album_artist, _ = Artist.get_or_create(name=artist_name)
        album.artist = resolvePrimaryArtist(album_artist)
        resolved_artist_id = album.artist.id
        if previous_artist_id != album.artist_id:
            changed_fields.append("artist")
    album.save()
    syncAlbumArtists(album, previousArtistId=previous_artist_id)

    logMetadataEvent(
        logging.INFO,
        "review_album_update",
        result="success",
        task_id=task.id,
        album_id=album.id,
        changed_fields=changed_fields,
        resolved_artist_id=resolved_artist_id,
    )

    return {"status": "success", "message": "album updated"}


@frontend.route("/metadata/review-tasks/<task_id>/tracks", methods=["POST"])
@admin_only
def update_metadata_review_task_tracks(task_id):
    task = None
    try:
        task = getMetadataReviewTask(task_id)
        ensurePendingReviewTask(task)
    except ValueError as exc:
        logMetadataEvent(logging.WARNING, "review_tracks_update", result="bad_request", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        logMetadataEvent(logging.WARNING, "review_tracks_update", result="not_found", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 404
    raw_data = request.get_json(silent=True) or {}
    track_updates = []
    for track_payload in raw_data.get("tracks", []):
        track = Track.get_or_none(Track.id == track_payload["id"])
        if track is None:
            logMetadataEvent(
                logging.WARNING,
                "review_tracks_update",
                result="not_found",
                task_id=task.id,
                album_id=task.album.id,
                track_id=track_payload["id"],
                processed_count=len(track_updates),
            )
            return {"status": "error", "message": "track not found"}, 404
        previous_artist_id = track.artist_id
        if track.album_id != task.album.id:
            logMetadataEvent(
                logging.WARNING,
                "review_tracks_update",
                result="bad_request",
                task_id=task.id,
                album_id=task.album.id,
                track_id=track.id,
                processed_count=len(track_updates),
            )
            return {"status": "error", "message": "track is outside this review task"}, 400

        track_updates.append((track, track_payload, previous_artist_id))

    with db.atomic():
        for track, track_payload, previous_artist_id in track_updates:
            if "number" in track_payload:
                track.number = track_payload["number"]
            if "title" in track_payload:
                track.title = track_payload["title"]
            artist_name = (track_payload.get("artist_name") or "").strip()
            if artist_name:
                track_artist, _ = Artist.get_or_create(name=artist_name)
                track.artist = resolvePrimaryArtist(track_artist)
            track.save()
            syncTrackArtists(track, previousArtistId=previous_artist_id)

    logMetadataEvent(
        logging.INFO,
        "review_tracks_update",
        result="success",
        task_id=task.id,
        album_id=task.album.id,
        track_count=len(track_updates),
    )

    return {"status": "success", "message": "tracks updated"}


@frontend.route("/metadata/review-tasks/<task_id>/artists/<artist_id>", methods=["POST"])
@admin_only
def update_metadata_review_task_artist(task_id, artist_id):
    task = None
    try:
        task = getMetadataReviewTask(task_id)
        ensurePendingReviewTask(task)
    except ValueError as exc:
        logMetadataEvent(
            logging.WARNING,
            "review_artist_update",
            result="bad_request",
            task_id=task_id,
            requested_artist_id=artist_id,
        )
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        logMetadataEvent(
            logging.WARNING,
            "review_artist_update",
            result="not_found",
            task_id=task_id,
            requested_artist_id=artist_id,
        )
        return {"status": "error", "message": str(exc)}, 404
    allowed_artist_ids = {artist.id for artist in getTaskRelatedArtists(task)}
    target_artist = Artist.get_or_none(Artist.id == artist_id)
    if target_artist is None:
        logMetadataEvent(
            logging.WARNING,
            "review_artist_update",
            result="not_found",
            task_id=task.id,
            album_id=task.album.id,
            requested_artist_id=artist_id,
        )
        return {"status": "error", "message": "artist not found"}, 404
    if target_artist.id not in allowed_artist_ids:
        logMetadataEvent(
            logging.WARNING,
            "review_artist_update",
            result="bad_request",
            task_id=task.id,
            album_id=task.album.id,
            requested_artist_id=artist_id,
            target_artist_id=target_artist.id,
        )
        return {"status": "error", "message": "artist is outside this review task"}, 400

    raw_data, artist_photo = getArtistMetadataRequestData()
    biography = raw_data.get("biography")
    primary_name = (raw_data.get("primary_name") or "").strip()
    primary_changed = bool(primary_name)
    biography_updated = biography is not None
    photo_updated = artist_photo is not None

    try:
        if primary_name:
            primary_artist, _ = Artist.get_or_create(name=primary_name)
            target_artist = assignPrimaryArtist(target_artist, primary_artist)
        if biography is not None or artist_photo is not None:
            updateArtistMetadata(
                current_app.config,
                target_artist,
                biography=biography,
                imageFile=artist_photo,
            )
    except ValueError as exc:
        logMetadataEvent(
            logging.WARNING,
            "review_artist_update",
            result="bad_request",
            task_id=task.id,
            album_id=task.album.id,
            requested_artist_id=artist_id,
            target_artist_id=target_artist.id,
            primary_changed=primary_changed,
            biography_updated=biography_updated,
            photo_updated=photo_updated,
        )
        return {"status": "error", "message": str(exc)}, 400

    logMetadataEvent(
        logging.INFO,
        "review_artist_update",
        result="success",
        task_id=task.id,
        album_id=task.album.id,
        requested_artist_id=artist_id,
        target_artist_id=target_artist.id,
        primary_changed=primary_changed,
        biography_updated=biography_updated,
        photo_updated=photo_updated,
    )

    return {"status": "success", "message": "artist updated"}


@frontend.route("/metadata/review-tasks/<task_id>/confirm", methods=["POST"])
@admin_only
def confirm_metadata_review_task(task_id):
    task = None
    try:
        task = getMetadataReviewTask(task_id)
        previous_status = task.status
        confirmMetadataReviewTask(task)
    except ValueError as exc:
        logMetadataEvent(logging.WARNING, "review_task_confirm", result="bad_request", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        logMetadataEvent(logging.WARNING, "review_task_confirm", result="not_found", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 404

    logMetadataEvent(
        logging.INFO,
        "review_task_confirm",
        result="success",
        task_id=task.id,
        album_id=task.album.id,
        from_status=previous_status,
        to_status=task.status,
    )

    redirectResponse = getReviewRedirectResponse(task)
    if redirectResponse is not None:
        return redirectResponse

    return {"status": "success", "message": "review task confirmed", "task_status": task.status}


@frontend.route("/metadata/review-tasks/<task_id>/dismiss", methods=["POST"])
@admin_only
def dismiss_metadata_review_task(task_id):
    task = None
    try:
        task = getMetadataReviewTask(task_id)
        previous_status = task.status
        dismissMetadataReviewTask(task)
    except ValueError as exc:
        logMetadataEvent(logging.WARNING, "review_task_dismiss", result="bad_request", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 400
    except LookupError as exc:
        logMetadataEvent(logging.WARNING, "review_task_dismiss", result="not_found", task_id=task_id)
        return {"status": "error", "message": str(exc)}, 404

    logMetadataEvent(
        logging.INFO,
        "review_task_dismiss",
        result="success",
        task_id=task.id,
        album_id=task.album.id,
        from_status=previous_status,
        to_status=task.status,
    )

    redirectResponse = getReviewRedirectResponse(task)
    if redirectResponse is not None:
        return redirectResponse

    return {"status": "success", "message": "review task dismissed", "task_status": task.status}


@frontend.route("/artists", methods=["GET", "POST"])
@admin_only
def metadata_artists():
    if request.method == "POST":
        raw_data, artist_photo = getArtistMetadataRequestData()
        action = raw_data.get("action")
        if action in ("change_primary_artist", "change_real_artist"):
            artist_id = raw_data.get("id")
            new_name = raw_data.get("primary_name") or raw_data.get("real_name")
            old_artist = Artist.get_by_id(artist_id)
            target_artist = resolvePrimaryArtist(old_artist)
            primary_changed = bool(new_name and new_name != raw_data['name'])
            biography = raw_data.get("biography")
            biography_updated = biography is not None
            photo_updated = artist_photo is not None

            if primary_changed:
                new_artist, status = Artist.get_or_create(name=new_name)
                # fill new_artist with old_artist's artist_info_json
                if status and old_artist.artist_info_json and not new_artist.artist_info_json:
                    new_artist.artist_info_json = old_artist.artist_info_json
                    new_artist.save()
            elif not (biography_updated or photo_updated):
                logMetadataEvent(
                    logging.INFO,
                    "artist_form_update",
                    result="no_change",
                    action=action,
                    artist_id=old_artist.id,
                    target_artist_id=target_artist.id,
                    primary_changed=primary_changed,
                    biography_updated=biography_updated,
                    photo_updated=photo_updated,
                )
                return {"status": "success", "message": "no change needed"}

            try:
                if primary_changed:
                    target_artist = assignPrimaryArtist(old_artist, new_artist)
                if biography is not None or artist_photo is not None:
                    updateArtistMetadata(
                        current_app.config,
                        target_artist,
                        biography=biography,
                        imageFile=artist_photo,
                    )
            except ValueError as exc:
                logMetadataEvent(
                    logging.WARNING,
                    "artist_form_update",
                    result="bad_request",
                    action=action,
                    artist_id=old_artist.id,
                    target_artist_id=target_artist.id,
                    primary_changed=primary_changed,
                    biography_updated=biography_updated,
                    photo_updated=photo_updated,
                )
                return {"status": "error", "message": str(exc)}, 400

            logMetadataEvent(
                logging.INFO,
                "artist_form_update",
                result="success",
                action=action,
                artist_id=old_artist.id,
                target_artist_id=target_artist.id,
                primary_changed=primary_changed,
                biography_updated=biography_updated,
                photo_updated=photo_updated,
            )

            responsePayload = {
                "status": "success",
                "artist": buildMetadataArtistCardData(target_artist),
                "removed_artist_id": str(old_artist.id) if primary_changed else None,
            }

            if primary_changed and (biography is not None or artist_photo is not None):
                responsePayload["message"] = "primary artist and metadata updated"
                return responsePayload
            if primary_changed:
                responsePayload["message"] = "primary artist updated"
                return responsePayload
            responsePayload["message"] = "artist metadata updated"
            return responsePayload
        return {"status": "success", "message": "artist metadata updated"}
        pass

    elif request.method == "GET":
        if request.args.get("embed"):
            return render_template("metadata-embedded.html")
        return render_template("metadata.html")


@frontend.route("/albums", methods=["GET", "POST"])
@admin_only
def metadata_album():
    if request.method == "POST":
        pass
    elif request.method == "GET":
        if request.args.get("embed"):
            return render_template("metadata-album-embedded.html")
        return render_template("metadata-album.html")
