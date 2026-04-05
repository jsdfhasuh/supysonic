# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Distributed under terms of the GNU AGPLv3 license.

import secrets
import uuid
from os.path import abspath
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from ..api.media import _get_cover_path
from ..db import Album, Artist, SharedTrackLink, Track
from . import frontend


share = Blueprint("share", __name__)


def getSharedTrack(token):
    link = SharedTrackLink.get_or_none(SharedTrackLink.token == token)
    if link is None or not link.enabled:
        abort(404)
    return link


@frontend.route("/share")
def share_index():
    links = list(
        SharedTrackLink.select()
        .where(SharedTrackLink.created_by == request.user)
        .order_by(SharedTrackLink.created_at.desc())
    )

    items = []
    for link in links:
        track = link.track
        artist_name = Artist.select(Artist.name).where(Artist.id == track.artist_id).scalar()
        album_name = Album.select(Album.name).where(Album.id == track.album_id).scalar()
        items.append(
            {
                "token": link.token,
                "enabled": link.enabled,
                "createdAt": link.created_at,
                "trackTitle": track.title,
                "artistName": artist_name,
                "albumName": album_name,
                "shareUrl": url_for("share.shared_track_page", token=link.token, _external=True),
            }
        )

    return render_template("shares.html", links=items)


@share.route("/share/track/<token>")
def shared_track_page(token):
    link = getSharedTrack(token)
    track = link.track
    artist_name = Artist.select(Artist.name).where(Artist.id == track.artist_id).scalar()
    album_name = Album.select(Album.name).where(Album.id == track.album_id).scalar()
    cover_eid = str(track.id) if track.has_art else f"al-{track.album_id}"
    return render_template(
        "share_track.html",
        share_link=link,
        track=track,
        artist_name=artist_name,
        album_name=album_name,
        current_url=url_for("share.shared_track_page", token=token, _external=True),
        stream_url=url_for("share.shared_track_stream", token=token),
        cover_url=url_for("share.shared_track_cover", token=token, eid=cover_eid),
    )


@share.route("/share/track/<token>/stream")
def shared_track_stream(token):
    link = getSharedTrack(token)
    track = link.track
    return send_file(abspath(track.path), mimetype=track.mimetype, conditional=True)


@share.route("/share/track/<token>/cover/<eid>")
def shared_track_cover(token, eid):
    getSharedTrack(token)
    try:
        cover_path = _get_cover_path(eid)
    except Exception:
        abort(404)
    return send_file(cover_path)


@frontend.route("/track/<tid>/share", methods=["GET", "POST"])
def create_track_share(tid):
    try:
        track_id = uuid.UUID(tid)
    except ValueError:
        if request.method == "POST":
            return jsonify({"status": "error", "message": "Invalid track id"}), 400
        flash("Invalid track id", "warning")
        return redirect(url_for("frontend.playlist_index"))

    track = Track.get_or_none(Track.id == track_id)
    if track is None:
        if request.method == "POST":
            return jsonify({"status": "error", "message": "Unknown track"}), 404
        flash("Unknown track", "warning")
        return redirect(url_for("frontend.playlist_index"))

    link = SharedTrackLink.create(
        token=secrets.token_urlsafe(24),
        track=track,
        created_by=request.user,
    )
    share_url = url_for("share.shared_track_page", token=link.token, _external=True)
    if request.method == "POST":
        return jsonify(
            {
                "status": "success",
                "shareUrl": share_url,
                "trackTitle": track.title,
                "artistName": Artist.select(Artist.name).where(Artist.id == track.artist_id).scalar(),
            }
        )

    referrer = request.referrer or url_for("frontend.playlist_index", _external=True)
    parts = list(urlparse(referrer))
    query = dict(parse_qsl(parts[4], keep_blank_values=True))
    query["share_url"] = share_url
    query["share_title"] = track.title
    parts[4] = urlencode(query)
    flash("Share link created.", "success")
    return redirect(urlunparse(parts))


@frontend.route("/share/track/<token>/disable")
def disable_track_share(token):
    link = SharedTrackLink.get_or_none(SharedTrackLink.token == token)
    if link is None:
        flash("Unknown share link", "warning")
        return redirect(url_for("frontend.share_index"))
    if link.created_by != request.user and not request.user.admin:
        flash("You are not allowed to manage this share link", "danger")
        return redirect(url_for("frontend.share_index"))

    link.enabled = False
    link.save()
    flash("Share link disabled.", "success")
    return redirect(url_for("frontend.share_index"))
