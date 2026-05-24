# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2018 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import logging
import time
import uuid
from typing import Any, List

from flask import request

from ..db import Playlist, User, Track, db, StarredTrack, random
from ..recommend import (
    getLatestRecommendedPlaylist,
    getRecommendedPlaylistForDay,
    non_recommended_playlist_where,
)
from ..recommendation_feedback import (
    HOT_RECOMMENDED_SCOPE,
    filter_disliked_recommended_tracks,
    get_disliked_recommended_song_ids,
    set_recommendation_feedback,
)
from . import get_entity, api_routing
from .exceptions import Forbidden, GenericError, MissingParameter

logger = logging.getLogger(__name__)


def _get_recommended_count() -> int:
    try:
        count = int(request.values.get("count") or 50)
    except (TypeError, ValueError):
        raise GenericError("Invalid recommended playlist count")
    return max(0, min(count, 500))


def _get_json_body_value(name: str, default: Any = None) -> Any:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload.get(name, default)
    return default


def _get_request_value(name: str, default: Any = None) -> Any:
    value = request.values.get(name)
    if value is not None:
        return value
    return _get_json_body_value(name, default)


def _collect_random_recommended_tracks(user, count: int) -> List[Track]:
    if count <= 0:
        return []
    disliked_song_ids = get_disliked_recommended_song_ids(user, HOT_RECOMMENDED_SCOPE)
    tracks = []
    seen_track_ids = set()
    query_limit = max(count * 3, 50)
    for track in Track.select().order_by(random()).limit(query_limit):
        track_id = str(track.id)
        if track_id in disliked_song_ids or track_id in seen_track_ids:
            continue
        tracks.append(track)
        seen_track_ids.add(track_id)
        if len(tracks) >= count:
            break
    return tracks


@api_routing("/getPlaylists")
def list_playlists():
    query = (
        Playlist.select()
        .where(
            (Playlist.user == request.user) | Playlist.public,
            non_recommended_playlist_where(),
        )
        .order_by(Playlist.name)
    )

    username = request.values.get("username")
    if username:
        if not request.user.admin:
            raise Forbidden()

        # get rather than join in the following query to raise an exception if the
        # requested user doesn't exist
        user = User.get(name=username)
        query = (
            Playlist.select()
            .where(Playlist.user == user, non_recommended_playlist_where())
            .order_by(Playlist.name)
        )
    temp = [p.as_subsonic_playlist(request.user) for p in query]
    return request.formatter(
        "playlists",
        {"playlist": temp},
    )


@api_routing("/getPlaylist")
def show_playlist():
    res = get_entity(Playlist)
    if (
        isinstance(res, Playlist)
        and res.user != request.user
        and not res.public
        and not request.user.admin
    ):
        raise Forbidden()
    if res == "default" and request.user:
        trq = (
            StarredTrack.select(StarredTrack.starred)
            .join(Track)
            .where(StarredTrack.user == request.user)
            .order_by(-StarredTrack.date)
        )
        first_album = trq[0].starred.album if trq else None
        info = {
            "id": "default",
            "name": "my Starred Tracks",
            "owner": request.user.name,
            "public": False,
            "comment": "Tracks you have starred",
            "songCount": len(trq),
            "duration": sum(t.starred.duration for t in trq),
            "created": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
        }
        if first_album:
            info["coverArt"] = f"al-{first_album.id}"
        entry = [
            st.starred.as_subsonic_child(request.user, request.client) for st in trq
        ]
        info["entry"] = entry
        return request.formatter("playlist", info)
    info = res.as_subsonic_playlist(request.user)
    info["entry"] = [
        t.as_subsonic_child(request.user, request.client) for t in res.get_tracks()
    ]
    return request.formatter("playlist", info)


@api_routing("/createPlaylist")
@db.atomic()
def create_playlist():
    playlist_id, name = map(request.values.get, ("playlistId", "name"))
    # songId actually doesn't seem to be required
    songs = request.values.getlist("songId")
    playlist_id = uuid.UUID(playlist_id) if playlist_id else None

    if playlist_id:
        playlist = Playlist[playlist_id]

        if playlist.user != request.user and not request.user.admin:
            raise Forbidden()

        playlist.clear()
        if name:
            playlist.name = name
    elif name:
        playlist = Playlist.create(user=request.user, name=name)
    else:
        raise MissingParameter("playlistId or name")

    for sid in songs:
        sid = uuid.UUID(sid)
        track = Track[sid]
        playlist.add(track)
    playlist.save()
    return request.formatter.empty


@api_routing("/deletePlaylist")
def delete_playlist():
    res = get_entity(Playlist)
    if res.user != request.user and not request.user.admin:
        raise Forbidden()

    res.delete_instance()
    return request.formatter.empty


@api_routing("/updatePlaylist")
def update_playlist():
    res = get_entity(Playlist, "playlistId")
    if res.user != request.user and not request.user.admin:
        raise Forbidden()

    playlist = res
    name, comment, public = map(request.values.get, ("name", "comment", "public"))
    to_add, to_remove = map(
        request.values.getlist, ("songIdToAdd", "songIndexToRemove")
    )

    if name:
        playlist.name = name
    if comment:
        playlist.comment = comment
    if public:
        playlist.public = public in (True, "True", "true", 1, "1")

    to_add = map(uuid.UUID, to_add)
    to_remove = map(int, to_remove)

    for sid in to_add:
        track = Track[sid]
        playlist.add(track)

    playlist.remove_at_indexes(to_remove)
    playlist.save()

    return request.formatter.empty


@api_routing("/getRecommendedPlaylists")
def get_recommended_playlists():
    user = request.user
    if not user:
        raise Forbidden()
    count = _get_recommended_count()
    recommended_playlist = getRecommendedPlaylistForDay(user)
    if recommended_playlist is None:
        recommended_playlist = getLatestRecommendedPlaylist(user)
    if recommended_playlist:
        recommended_tracks = filter_disliked_recommended_tracks(
            user,
            recommended_playlist.get_tracks(),
            scope=HOT_RECOMMENDED_SCOPE,
        )[:count]
        info = recommended_playlist.as_subsonic_playlist(
            request.user,
            tracks=recommended_tracks,
        )
        info["entry"] = [
            t.as_subsonic_child(request.user, request.client)
            for t in recommended_tracks
        ]
        return request.formatter("playlist", info)
    else:
        # temp return a random playlist for the user if not exist
        trs = _collect_random_recommended_tracks(user, count)
        info = {
            "id": "Recommended",
            "name": "Recommended Playlist",
            "owner": request.user.name,
            "public": False,
            "comment": "recommended playlist for you",
            "songCount": len(trs),
            "duration": sum(t.duration for t in trs),
            "created": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
        }
        first_track = trs[0] if trs else None
        if first_track:
            info["coverArt"] = f"al-{first_track.album.id}"
        entry = [st.as_subsonic_child(request.user, request.client) for st in trs]
        info["entry"] = entry
        return request.formatter("playlist", info)


@api_routing("/setRecommendationFeedback")
def set_recommendation_feedback_api():
    user = request.user
    if not user:
        raise Forbidden()

    song_id = _get_request_value("id")
    action = _get_request_value("action")
    scope = _get_request_value("scope", HOT_RECOMMENDED_SCOPE)
    reason = _get_request_value("reason", "user_dislike")
    source = _get_request_value("source", "api")

    if not song_id:
        raise MissingParameter("id")
    if not action:
        raise MissingParameter("action")

    try:
        feedback = set_recommendation_feedback(
            user,
            song_id=song_id,
            action=action,
            scope=scope,
            reason=reason,
            source=source,
        )
    except ValueError as exc:
        raise GenericError(str(exc))

    return request.formatter(
        "recommendationFeedback",
        {
            "id": feedback.song_id,
            "action": feedback.action,
            "scope": feedback.scope,
        },
    )
