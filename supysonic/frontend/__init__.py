# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2022 Alban 'spl0k' Féron
#                    2017 Óscar García Amor
#
# Distributed under terms of the GNU AGPLv3 license.

import json
import os
import time
from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    render_template,
    send_file,
    session,
    url_for,
)
from PIL import Image
from flask import Blueprint
from functools import wraps
from ..covers import EXTENSIONS
from .. import VERSION, DOWNLOAD_URL
from ..daemon.client import DaemonClient
from ..daemon.exceptions import DaemonUnavailableError
from ..db import Artist, Album, EmoPlaybackState, EmoSessionQueue, Track
from ..api.media import _get_cover_path
from ..emo.ws_state import get_state
from ..managers.user import UserManager
from ..api.media import __new_get_cover_path
from ..cache import CacheMiss
frontend = Blueprint("frontend", __name__)
state = get_state()


@frontend.context_processor
def inject_metadata():
    return {"version": VERSION, "download_url": DOWNLOAD_URL}


@frontend.before_request
def login_check():
    request.user = None 
    should_login = True
    if session.get("userid"):
        try:
            user = UserManager.get(session.get("userid"))
            request.user = user
            should_login = False
        except (ValueError, User.DoesNotExist):
            session.clear()

    if should_login and request.endpoint != "frontend.login":
        flash("Please login")
        return redirect(
            url_for(
                "frontend.login",
                returnUrl=request.script_root
                + request.url[len(request.url_root) - 1 :],
            )
        )


@frontend.before_request
def scan_status():
    if not request.user or not request.user.admin:
        return

    try:
        scanned = DaemonClient(
            current_app.config["DAEMON"]["socket"]
        ).get_scanning_progress()
        if scanned is not None:
            flash(f"Scanning in progress, {scanned} files scanned.")
    except DaemonUnavailableError:
        pass


@frontend.route("/")
def index():
    device_rows = getDeviceMonitorRows() if request.user and request.user.admin else []
    device_summary = getDeviceMonitorSummary(device_rows) if request.user and request.user.admin else None
    stats = {
        "artists": Artist.select().count(),
        "albums": Album.select().count(),
        "tracks": Track.select().count(),
    }
    return render_template(
        "home.html",
        stats=stats,
        device_summary=device_summary,
        recent_devices=device_rows[:5],
    )


def admin_only(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if not request.user or not request.user.admin:
            return redirect(url_for("frontend.index"))
        return f(*args, **kwargs)

    return decorated_func


def getConnectedDevices(user_name=None):
    devices = state.list_clients(user_name=user_name)
    devices.sort(key=lambda item: (item.get("userName", ""), item.get("deviceName", "")))
    return devices


def getDeviceMonitorRows(user_name=None):
    devices = getConnectedDevices(user_name=user_name)
    session_ids = sorted({d.get("sessionId") for d in devices if d.get("sessionId")})

    playback_by_session = {}
    queue_by_session = {}
    song_meta = {}

    if session_ids:
        all_song_ids = set()

        for record in EmoPlaybackState.select().where(
            EmoPlaybackState.session_id.in_(session_ids)
        ):
            if record.track_id:
                all_song_ids.add(str(record.track_id))
            playback_by_session[record.session_id] = {
                "state": record.state,
                "trackId": record.track_id,
                "positionMs": record.position_ms,
                "volume": record.volume,
                "updatedAt": record.updated_at.timestamp(),
            }

        for record in EmoSessionQueue.select().where(
            EmoSessionQueue.session_id.in_(session_ids)
        ):
            queue_song_ids = json.loads(record.queue_json)
            all_song_ids.update(str(song_id) for song_id in queue_song_ids)
            queue_by_session[record.session_id] = {
                "queueSongIds": queue_song_ids,
                "queueCount": len(queue_song_ids),
                "currentIndex": record.current_index,
                "queuePositionMs": record.position_ms,
                "currentQueueSongId": (
                    queue_song_ids[record.current_index]
                    if queue_song_ids and 0 <= record.current_index < len(queue_song_ids)
                    else None
                ),
                "updatedAt": record.updated_at.timestamp(),
            }

        if all_song_ids:
            for track in Track.select(Track, Artist).join(Artist).where(Track.id.in_(all_song_ids)):
                song_meta[str(track.id)] = {
                    "title": track.title,
                    "artist": track.artist.get_artist_name(),
                }

    rows = []
    for device in devices:
        session_id = device.get("sessionId")
        playback = playback_by_session.get(session_id, {})
        queue = queue_by_session.get(session_id, {})
        row = dict(device)
        row.update(playback)
        row.update(queue)
        if row.get("trackId"):
            row["trackLabel"] = song_meta.get(str(row["trackId"]), {}).get("title")
            artist_name = song_meta.get(str(row["trackId"]), {}).get("artist")
            if row.get("trackLabel") and artist_name:
                row["trackLabel"] = f"{row['trackLabel']} - {artist_name}"
            row["trackCoverUrl"] = url_for("frontend.device_cover", eid=row["trackId"])
        queue_labels = []
        queue_entries = []
        for song_id in row.get("queueSongIds") or []:
            meta = song_meta.get(str(song_id))
            if meta is None:
                label = str(song_id)
            elif meta.get("artist"):
                label = f"{meta['title']} - {meta['artist']}"
            else:
                label = meta["title"]
            queue_labels.append(label)
            queue_entries.append(
                {
                    "songId": str(song_id),
                    "label": label,
                    "isCurrent": str(song_id) == str(row.get("currentQueueSongId")),
                }
            )
        row["queueSongLabels"] = queue_labels
        row["queueEntries"] = queue_entries
        if row.get("currentQueueSongId"):
            current_meta = song_meta.get(str(row["currentQueueSongId"]))
            if current_meta is not None:
                row["currentQueueSongLabel"] = (
                    f"{current_meta['title']} - {current_meta['artist']}"
                    if current_meta.get("artist")
                    else current_meta["title"]
                )
            row["currentQueueSongCoverUrl"] = url_for(
                "frontend.device_cover", eid=row["currentQueueSongId"]
            )
        row["lastUpdatedAt"] = playback.get("updatedAt") or queue.get("updatedAt")
        rows.append(row)

    rows.sort(
        key=lambda item: (
            item.get("userName", ""),
            item.get("sessionId", ""),
            item.get("deviceName", ""),
        )
    )
    return rows


def getDeviceMonitorSummary(rows):
    session_ids = {row.get("sessionId") for row in rows if row.get("sessionId")}
    playing_sessions = {
        row.get("sessionId")
        for row in rows
        if row.get("sessionId") and row.get("state") == "playing"
    }
    recently_updated = sum(1 for row in rows if row.get("lastUpdatedAt"))
    return {
        "onlineDevices": len(rows),
        "activeSessions": len(session_ids),
        "playingSessions": len(playing_sessions),
        "recentlyUpdated": recently_updated,
    }


@frontend.route("/devices")
@admin_only
def device_index():
    rows = getDeviceMonitorRows()
    return render_template(
        "devices.html",
        devices=rows,
        summary=getDeviceMonitorSummary(rows),
    )


@frontend.route("/devices/data")
@admin_only
def device_data():
    rows = getDeviceMonitorRows()
    return jsonify({"devices": rows, "summary": getDeviceMonitorSummary(rows)})


@frontend.route("/devices/cover/<eid>")
@admin_only
def device_cover(eid):
    
    cache = current_app.cache

    target_track = Track.select().where(Track.id == eid).first()
    album = target_track.album if target_track else None
    new_eid = f"al-{album.id}" if album else None
    print(f"eid: {eid}")
    input_size = request.values.get("input_size", "")
    cover_path = __new_get_cover_path(new_eid, input_size)

    if not cover_path:
        abort(404, description="Cover art not found")
    elif not os.path.isfile(cover_path):
        abort(404, description="Cover art file not found")

    size = request.values.get("size")
    if size:
        size = int(size)
    else:
        # If the cover was extracted from a track it won't have an accurate
        # extension for Flask to derive the mimetype from - derive it from the
        # contents instead.
        mimetype = None
        if os.path.splitext(cover_path)[1].lower() not in EXTENSIONS:
            with Image.open(cover_path) as im:
                mimetype = f"image/{im.format.lower()}"
        return send_file(cover_path, mimetype=mimetype)

    with Image.open(cover_path) as im:
        mimetype = f"image/{im.format.lower()}"
        if size > im.width and size > im.height:
            return send_file(cover_path, mimetype=mimetype)

        cache_key = f"{eid}-cover-{size}"
        try:
            return send_file(cache.get(cache_key), mimetype=mimetype)
        except CacheMiss:
            im.thumbnail([size, size], Image.Resampling.LANCZOS)
            with cache.set_fileobj(cache_key) as fp:
                im.save(fp, im.format)
            return send_file(cache.get(cache_key), mimetype=mimetype)


from .user import *
from .folder import *
from .playlist import *
from .metadata import *
from .share import *
