# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2018 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import uuid

from flask import request

from ..db import Playlist, User, Track, db, StarredTrack, random
from ..TaskManger import get_task_manager, TaskManager
from ..recommend import create_recommend_playlist
from . import get_entity, api_routing
from .exceptions import Forbidden, MissingParameter
import time
import logging

logger = logging.getLogger(__name__)
@api_routing("/getPlaylists")
def list_playlists():
    query = (
        Playlist.select()
        .orwhere(Playlist.user == request.user, Playlist.public)
        .order_by(Playlist.name)
    )

    username = request.values.get("username") or request.values.get("u")
    if username:
        if not request.user.admin:
            raise Forbidden()

        # get rather than join in the following query to raise an exception if the
        # requested user doesn't exist
        user = User.get(name=username)
        query = Playlist.select().where(Playlist.user == user).order_by(Playlist.name)
        # add star to indicate
        trq = (
            StarredTrack.select(StarredTrack.starred)
            .join(Track)
            .where(StarredTrack.user == request.user)
            .order_by(-StarredTrack.date)
        )
        first_track = trq[0].starred if trq else None
        first_album = first_track.album if first_track else None

        favourite_playlist = {
            'id': 'default',
            'name': 'my Starred Tracks',
            'owner': user.name,
            'public': False,
            'comment': 'Tracks you have starred',
            'songCount': len(trq),
            'duration': sum(t.starred.duration for t in trq),
            'created': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            'changed': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            "coverArt": f"al-{first_album.id}" if first_album else None,
        }
    temp = [p.as_subsonic_playlist(request.user) for p in query]
    temp.insert(0, favourite_playlist)
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
        first_album = trq[0].album if trq else None
        info = {
            "id": "default",
            "name": "my Starred Tracks",
            "owner": request.user.name,
            "public": False,
            "comment": "Tracks you have starred",
            "songCount": len(trq),
            "duration": sum(t.starred.duration for t in trq),
            "created": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            "changed": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            "coverArt": f"al-{first_album.id}",
        }
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
    info = playlist.as_subsonic_playlist(request.user)
    info["entry"] = [
        t.as_subsonic_child(request.user, request.client) for t in playlist.get_tracks()
    ]

    return request.formatter("playlist", info)


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
    today = time.strftime('%Y-%m-%d', time.gmtime())
    today_playlist = (
        Playlist.select()
        .where(
            (Playlist.user == user)
            & (Playlist.name == f"{user.name}'s {today} recommend playlist")
        )
        .first()
    )
    if not today_playlist and user:
        logger.info(f"Submitting task to create recommend playlist for user {user.name}")
        TaskManager_instance = get_task_manager()
        task_id = f"create_recommend_playlist_{user.id}_{today}"
        TaskManager_instance.submit_task(
            task_id=task_id, func=create_recommend_playlist, num_songs=50, user=user
        )
    if not user:
        raise Forbidden()
    recommended_playlist = (
        today_playlist
        if today_playlist
        else Playlist.select()
        .where((Playlist.user == user) & (Playlist.comment == "recommended"))
        .order_by(Playlist.created.desc())
        .first()
    )
    if recommended_playlist:
        info = recommended_playlist.as_subsonic_playlist(request.user)
        info["entry"] = [
            t.as_subsonic_child(request.user, request.client)
            for t in recommended_playlist.get_tracks()
        ]
        return request.formatter("playlist", info)
    else:
        # temp return a random playlist for the user if not exist
        trs = Track.select().order_by(random()).limit(50)
        info = {
            "id": "Recommended",
            "name": "Recommended Playlist",
            "owner": request.user.name,
            "public": False,
            "comment": "recommended playlist for you",
            "songCount": len(trs),
            "duration": sum(t.duration for t in trs),
            "created": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
            "changed": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
        }
        entry = [st.as_subsonic_child(request.user, request.client) for st in trs]
        info["entry"] = entry
        return request.formatter("playlist", info)
