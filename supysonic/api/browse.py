# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2013-2022 Alban 'spl0k' Féron
#
# Distributed under terms of the GNU AGPLv3 license.

import re
import string

from flask import current_app, request
from peewee import fn

from ..db import Folder, Artist, Album, Track

from . import get_entity, get_root_folder, api_routing, get_entity_by_name


@api_routing("/getMusicFolders")
def list_folders():
    return request.formatter(
        "musicFolders",
        {
            "musicFolder": [
                {"id": str(f.id), "name": f.name}
                for f in Folder.select().where(Folder.root).order_by(Folder.name)
            ]
        },
    )


def build_ignored_articles_pattern():
    articles = current_app.config["WEBAPP"]["index_ignored_prefixes"]
    if articles is None:
        return None

    articles = articles.split()
    if not articles:
        return None

    return r"^(" + r" |".join(re.escape(a) for a in articles) + r" )"


def ignored_articles_str():
    articles = current_app.config["WEBAPP"]["index_ignored_prefixes"]
    if articles is None:
        return ""

    return " ".join(articles.split())


def build_indexes(source):
    indexes = {}
    pattern = build_ignored_articles_pattern()
    for item in source:
        name = item.name or ""  # 确保 name 不是 None
        if not name.strip():  # 检查名称是否为空或只包含空格
            index = "?"
        else:
            if pattern:
                name = re.sub(pattern, "", name, flags=re.I)
            index = name[0].upper()
            if index in string.digits:
                index = "#"
            elif index not in string.ascii_letters:
                index = "?"

        if index not in indexes:
            indexes[index] = []

        indexes[index].append((item, name))

    return indexes


@api_routing("/getIndexes")
def list_indexes():
    musicFolderId = request.values.get("musicFolderId")
    ifModifiedSince = request.values.get("ifModifiedSince")
    if ifModifiedSince:
        ifModifiedSince = int(ifModifiedSince) / 1000

    if musicFolderId is None:
        folders = Folder.select().where(Folder.root)[:]
    else:
        folders = [get_root_folder(musicFolderId)]

    last_modif = max(f.last_scan for f in folders)
    if ifModifiedSince is not None and last_modif < ifModifiedSince:
        return request.formatter(
            "indexes",
            {
                "lastModified": last_modif * 1000,
                "ignoredArticles": ignored_articles_str(),
            },
        )

    # The XSD lies, we don't return artists but a directory structure
    artists = []
    children = []
    for f in folders:
        artists += f.children[:]
        children += f.tracks[:]

    indexes = build_indexes(artists)
    return request.formatter(
        "indexes",
        {
            "lastModified": last_modif * 1000,
            "ignoredArticles": ignored_articles_str(),
            "index": [
                {
                    "name": k,
                    "artist": [
                        a.as_subsonic_artist(request.user)
                        for a, _ in sorted(v, key=lambda t: t[1].lower())
                    ],
                }
                for k, v in sorted(indexes.items())
            ],
            "child": [
                c.as_subsonic_child(request.user, request.client)
                for c in sorted(children, key=lambda t: t.sort_key())
            ],
        },
    )


@api_routing("/getMusicDirectory")
def show_directory():
    res = get_entity(Folder)
    return request.formatter(
        "directory", res.as_subsonic_directory(request.user, request.client)
    )


@api_routing("/getGenres")
def list_genres():
    return request.formatter(
        "genres",
        {
            "genre": [
                {"value": genre, "songCount": sc, "albumCount": ac}
                for genre, sc, ac in Track.select(
                    Track.genre, fn.count("*"), fn.count(Track.album.distinct())
                )
                .where(Track.genre.is_null(False))
                .group_by(Track.genre)
                .tuples()
            ]
        },
    )


@api_routing("/getTopSongs")
def top_songs():
    res = get_entity_by_name(Artist, param='artist')
    # 获取该艺人下按播放次数排序的前 10 首歌曲
    tracks = res.tracks.select().order_by(Track.play_count.desc())
    topSongs = [
        track.as_subsonic_child(request.user, request.client) for track in tracks
    ]
    return request.formatter("topSongs", {"song": topSongs})


@api_routing("/getArtists")
def list_artists():
    mfid = request.values.get("musicFolderId")

    query = Artist.select()
    if mfid is not None:
        folder = get_root_folder(mfid)
        query = Artist.select().join(Track).where(Track.root_folder == folder)

    indexes = build_indexes(query)
    return request.formatter(
        "artists",
        {
            "ignoredArticles": ignored_articles_str(),
            "index": [
                {
                    "name": k,
                    "artist": [
                        a.as_subsonic_artist(request.user)
                        for a, _ in sorted(v, key=lambda t: t[1].lower())
                    ],
                }
                for k, v in sorted(indexes.items())
            ],
        },
    )


@api_routing("/getArtist")
def artist_info():
    res = get_entity(Artist)
    info = res.as_subsonic_artist(request.user)
    albums = set(res.albums)
    albums |= {t.album for t in res.tracks}
    albums |= {rel.album_id for rel in res.artist_albums}
    info["album"] = [
        a.as_subsonic_album(request.user)
        for a in sorted(albums, key=lambda a: a.sort_key())
    ]

    return request.formatter("artist", info)


@api_routing("/getArtistInfo2")
def artist_info2():
    id = request.values.get("id")
    image_base_url = request.url.replace("/getArtistInfo2", "/getCoverArt")
    image_base_url = image_base_url.replace(f"{id}", f"ar-{id}")

    res = get_entity(Artist)
    info = res.get_info()
    info['smallImageUrl'] = f"{image_base_url}&input_size=small"
    info['mediumImageUrl'] = f"{image_base_url}&input_size=medium"
    info['largeImageUrl'] = f"{image_base_url}&input_size=large"

    # Add similar artists if available
    similar_artists = []
    # for artist in Artist.select().order_by(fn.random()).limit(8):
    #     if artist.id != res.id:
    #         similar_info = {
    #             "id": str(artist.id),
    #             "name": artist.name,
    #         }
    #         # Add album count
    #         album_count = len(set(artist.albums) | {t.album for t in artist.tracks})
    #         if album_count > 0:
    #             similar_info["albumCount"] = album_count

    #         similar_artists.append(similar_info)

    if similar_artists:
        info["similarArtist"] = similar_artists

    return request.formatter("artistInfo2", info)


@api_routing("/getAlbum")
def album_info():
    res = get_entity(Album)
    info = res.as_subsonic_album(request.user)
    info["song"] = [
        t.as_subsonic_child(request.user, request.client)
        for t in sorted(res.tracks, key=lambda t: t.sort_key())
    ]

    return request.formatter("album", info)


@api_routing("/getSong")
def track_info():
    res = get_entity(Track)
    return request.formatter(
        "song", res.as_subsonic_child(request.user, request.client)
    )
