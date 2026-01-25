# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2023 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

from datetime import timedelta
from flask import request
from peewee import fn, JOIN

from ..db import (
    Folder,
    Artist,
    Album,
    Track,
    StarredFolder,
    StarredArtist,
    StarredAlbum,
    StarredTrack,
    RatingFolder,
    User,
    User_Play_Activity,
)
from ..db import now, random

from . import api_routing, get_root_folder
from .exceptions import GenericError


@api_routing("/getRandomSongs")
def rand_songs():
    size = request.values.get("size", "10")
    genre, fromYear, toYear, musicFolderId = map(
        request.values.get, ("genre", "fromYear", "toYear", "musicFolderId")
    )

    size = int(size) if size else 10
    fromYear = int(fromYear) if fromYear else None
    toYear = int(toYear) if toYear else None
    root = get_root_folder(musicFolderId)

    query = Track.select()
    if fromYear:
        query = query.where(Track.year >= fromYear)
    if toYear:
        query = query.where(Track.year <= toYear)
    if genre:
        query = query.where(Track.genre == genre)
    if root:
        query = query.where(Track.root_folder == root)

    return request.formatter(
        "randomSongs",
        {
            "song": [
                t.as_subsonic_child(request.user, request.client)
                for t in query.order_by(random()).limit(size)
            ]
        },
    )


@api_routing("/getAlbumList")
def album_list():
    ltype = request.values["type"]

    size, offset, mfid = map(request.values.get, ("size", "offset", "musicFolderId"))
    size = int(size) if size else 10
    offset = int(offset) if offset else 0
    root = get_root_folder(mfid)

    query = Folder.select().join(Track, on=Track.folder).switch().group_by(Folder.id)
    if root is not None:
        query = query.where(Track.root_folder == root)

    if ltype == "random":
        return request.formatter(
            "albumList",
            {
                "album": [
                    f.as_subsonic_child(request.user)
                    for f in query.order_by(random()).limit(size)
                ]
            },
        )
    elif ltype == "newest":
        query = query.order_by(Folder.created.desc())
    elif ltype == "highest":
        query = query.join(RatingFolder, JOIN.LEFT_OUTER).order_by(
            fn.avg(RatingFolder.rating).desc()
        )
    elif ltype == "frequent":
        query = query.order_by(fn.avg(Track.play_count).desc())
    elif ltype == "recent":
        query = query.where(Track.last_play.is_null(False)).order_by(
            fn.max(Track.last_play).desc()
        )
    elif ltype == "starred":
        query = query.join(StarredFolder).where(StarredFolder.user == request.user)
    elif ltype == "alphabeticalByName":
        query = query.order_by(Folder.name)
    elif ltype == "alphabeticalByArtist":
        parent = Folder.alias()
        query = (
            query.join(parent)
            .group_by_extend(parent.id)
            .order_by(parent.name, Folder.name)
        )
    elif ltype == "byYear":
        startyear = int(request.values["fromYear"])
        endyear = int(request.values["toYear"])
        query = query.where(
            Track.year.between(min(startyear, endyear), max(startyear, endyear))
        )
        order = fn.min(Track.year)
        if endyear < startyear:
            order = order.desc()
        query = query.order_by(order)
    elif ltype == "byGenre":
        genre = request.values["genre"]
        query = query.where(Track.genre == genre)
    else:
        raise GenericError("Unknown search type")

    return request.formatter(
        "albumList",
        {
            "album": [
                f.as_subsonic_child(request.user)
                for f in query.limit(size).offset(offset)
            ]
        },
    )


@api_routing("/getAlbumList2")
def album_list_id3():
    ltype = request.values["type"]
    size, offset, mfid = map(request.values.get, ("size", "offset", "musicFolderId"))
    size = int(size) if size else 10
    offset = int(offset) if offset else 0
    root = get_root_folder(mfid)
    query = Album.select().join(Track).group_by(Album.id)
    if root is not None:
        query = query.where(Track.root_folder == root)
    result_albums = []
    added_albums = set()
    if ltype == "random":
        return request.formatter(
            "albumList2",
            {
                "album": [
                    a.as_subsonic_albumas_subsonic_album(request.user,request.client.client_name)
                    for a in query.order_by(random()).limit(size)
                ]
            },
        )
    elif ltype == "newest":
        query = query.order_by(fn.min(Track.created).desc())
    elif ltype == "frequent":
        frequent_albums = []
        frequent_albums_ids = {}
        play_activity_query = User_Play_Activity.select().where(
            User_Play_Activity.user == request.user
        )
        for activity in play_activity_query:
            album = activity.track.album
            frequent_albums.append(album)
            if album.id not in frequent_albums_ids:
                frequent_albums_ids[album.id] = 1
            else:
                frequent_albums_ids[album.id] += 1
        sorted_albums = sorted(
            frequent_albums, key=lambda a: frequent_albums_ids[a.id], reverse=True
        )

        for a in sorted_albums[:size]:
            if a.id not in added_albums:
                result_albums.append(a.as_subsonic_album(request.user,request.client.client_name))
                added_albums.add(a.id)

        if len(result_albums) >= size:
            query = []
        else:
            query = query.where(Track.last_play.is_null(False)).order_by(
                fn.avg(Track.play_count).desc()
            )
    elif ltype == "recent":
        # 收集最近播放的专辑
        recent_albums = []
        seen_album_ids = set()
        play_activity_query = (
            User_Play_Activity.select()
            .where(User_Play_Activity.user == request.user)
            .order_by(User_Play_Activity.time.desc())
        )
        for activity in play_activity_query:  # 获取更多记录以应对重复
            album = activity.track.album
            if album.id not in seen_album_ids:
                recent_albums.append(album)
                seen_album_ids.add(album.id)
            if len(recent_albums) >= size:
                break
        print(f"Found {len(recent_albums)} recent albums")

        if len(result_albums) >= size:
            query = []
        else:
            query = query.where(Track.last_play.is_null(False)).order_by(
                fn.max(Track.last_play).desc()
            )
        for a in recent_albums:
            if a.id not in added_albums:
                result_albums.append(a.as_subsonic_album(request.user,request.client.client_name))
                added_albums.add(a.id)
    elif ltype == "starred":
        query = (
            query.switch().join(StarredAlbum).where(StarredAlbum.user == request.user)
        )
    elif ltype == "alphabeticalByName":
        query = query.order_by(Album.name)
    elif ltype == "alphabeticalByArtist":
        query = (
            query.switch()
            .join(Artist)
            .group_by_extend(Artist.id)
            .order_by(Artist.name, Album.name)
        )
    elif ltype == "byYear":
        startyear = int(request.values["fromYear"])
        endyear = int(request.values["toYear"])
        query = query.having(
            fn.min(Track.year).between(min(startyear, endyear), max(startyear, endyear))
        )
        order = fn.min(Track.year)
        if endyear < startyear:
            order = order.desc()
        query = query.order_by(order)
    elif ltype == "byGenre":
        genre = request.values["genre"]
        query = query.where(Track.genre == genre)
    else:
        raise GenericError("Unknown search type")
    if len(result_albums) < size:
        for a in query.limit(size).offset(offset):
            if a.id not in added_albums:
                result_albums.append(a.as_subsonic_album(request.user,request.client.client_name))
                added_albums.add(a.id)
    else:
        result_albums = result_albums[offset:size]
    return request.formatter(
        "albumList2",
        {"album": result_albums},
    )


@api_routing("/getSongsByGenre")
def songs_by_genre():
    genre = request.values["genre"]

    count, offset, mfid = map(request.values.get, ("count", "offset", "musicFolderId"))
    count = int(count) if count else 10
    offset = int(offset) if offset else 0
    root = get_root_folder(mfid)

    query = Track.select().where(Track.genre == genre)
    if root is not None:
        query = query.where(Track.root_folder == root)
    return request.formatter(
        "songsByGenre",
        {
            "song": [
                t.as_subsonic_child(request.user, request.client)
                for t in query.limit(count).offset(offset)
            ]
        },
    )


@api_routing("/getNowPlaying")
def now_playing():
    query = User.select().where(
        User.last_play.is_null(False),
        User.last_play_date > now() - timedelta(minutes=3),
    )

    return request.formatter(
        "nowPlaying",
        {
            "entry": [
                {
                    **u.last_play.as_subsonic_child(request.user, request.client),
                    "username": u.name,
                    "minutesAgo": (now() - u.last_play_date).seconds / 60,
                    "playerId": 0,
                }
                for u in query
            ]
        },
    )


@api_routing("/getStarred")
def get_starred():
    mfid = request.values.get("musicFolderId")
    root = get_root_folder(mfid)

    folders = (
        StarredFolder.select(StarredFolder.starred)
        .join(Folder)
        .join(Track, on=Track.folder)
        .where(StarredFolder.user == request.user)
        .group_by(Folder)
    )
    if root is not None:
        folders = folders.where(Folder.path.startswith(root.path))

    arq = folders.having(fn.count(Track.id) == 0)
    alq = folders.having(fn.count(Track.id) > 0)
    trq = (
        StarredTrack.select(StarredTrack.starred)
        .join(Track)
        .where(StarredTrack.user == request.user)
        .order_by(-StarredTrack.date)
    )

    if root is not None:
        trq = trq.where(Track.root_folder == root)

    return request.formatter(
        "starred",
        {
            "artist": [sf.starred.as_subsonic_artist(request.user) for sf in arq],
            "album": [sf.starred.as_subsonic_child(request.user) for sf in alq],
            "song": [
                st.starred.as_subsonic_child(request.user, request.client) for st in trq
            ],
        },
    )


@api_routing("/getStarred2")
def get_starred_id3():
    mfid = request.values.get("musicFolderId")
    root = get_root_folder(mfid)

    arq = (
        StarredArtist.select(StarredArtist.starred)
        .join(Artist)
        .where(StarredArtist.user == request.user)
    )
    alq = (
        StarredAlbum.select(StarredAlbum.starred)
        .join(Album)
        .where(StarredAlbum.user == request.user)
    )
    trq = (
        StarredTrack.select(StarredTrack.starred)
        .join(Track)
        .where(StarredTrack.user == request.user)
    )

    if root is not None:
        arq = arq.join(Track).where(Track.root_folder == root)
        alq = alq.join(Track).where(Track.root_folder == root)
        trq = trq.where(Track.root_folder == root)

    return request.formatter(
        "starred2",
        {
            "artist": [sa.starred.as_subsonic_artist(request.user) for sa in arq],
            "album": [sa.starred.as_subsonic_album(request.user,request.client.client_name) for sa in alq],
            "song": [
                st.starred.as_subsonic_child(request.user, request.client) for st in trq
            ],
        },
    )
