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
from ..lastfm import LastFm
from ..db import Folder, Artist, Album, Track
from ..TaskManger import get_task_manager,TaskManager
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
    def get_web_play_count(lfm:LastFm, artist_name: str,all_tracks: list[Track]):
        # 通过lastfm查找播放次数
        real_track = []
        lfm_tracks = lfm.get_top_tracks(artist_name, limit=30)
        for lt in lfm_tracks['toptracks']['track']:
            for t in all_tracks:
                name = t.title
                if name.lower() == lt['name'].lower():
                    if t in real_track:
                        continue
                    real_track.append(t)
                    t.play_count_web = lt['playcount']
                    t.save()

    res = get_entity_by_name(Artist, param='artist')
    lfm = LastFm(current_app.config["LASTFM"], request.user)
    # find top songs by play_count_web
    all_tracks = Track.select().where(Track.artist == res)
    tracks_web_played = [t for t in all_tracks if t.play_count_web and t.play_count_web > 0]
    if tracks_web_played:
        tracks = sorted(tracks_web_played, key=lambda x: x.play_count_web, reverse=True)
        remain_tracks = [t for t in all_tracks if t not in tracks]
        tracks += sorted(remain_tracks, key=lambda x: x.play_count, reverse=True)
        return request.formatter(
            "topSongs",
            {
                "song": [
                    track.as_subsonic_child(request.user, request.client) for track in tracks
                ]
            },
        )
    if not lfm.get_enabled():
        tracks = (
            Track.select()
            .where(Track.artist == res)
            .order_by(Track.play_count.desc())
        )
    else:
        # 通过lastfm查找播放次数
        TaskManager_instance = get_task_manager()
        task_id = f"top_songs_{res.id}_{request.user.id}"
        TaskManager_instance.submit_task(task_id=task_id,func=get_web_play_count,lfm=lfm,artist_name=res.name,all_tracks=all_tracks)
    # 获取该艺人下按播放次数排序的前 10 首歌曲
    tracks = all_tracks.order_by(Track.play_count.desc())
    topSongs = [
        track.as_subsonic_child(request.user, request.client) for track in tracks
    ]
    return request.formatter("topSongs", {"song": topSongs})


@api_routing("/getArtists")
def list_artists():
    mfid = request.values.get("musicFolderId")

    query = Artist.select().where(Artist.real_artist.is_null())
    # query = Artist.select()# # 只选择主艺人
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
        a.as_subsonic_album(request.user,request.client.client_name)
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
    info = res.as_subsonic_album(request.user,request.client.client_name)
    info["song"] = [
        t.as_subsonic_child(request.user, request.client)
        for t in sorted(res.tracks, key=lambda t: t.sort_key())
    ]
    image_base_url = request.url.replace("/getAlbumInfo2", "/getCoverArt")
    image_base_url = image_base_url.replace(f"{res.id}", f"al-{res.id}")
    info['cover_art'] = f'{image_base_url}&input_size=large'
    return request.formatter("album", info)

@api_routing("/getAlbumInfo2")
def album_info2():
    res = get_entity(Album)
    info = res.as_subsonic_album(request.user,request.client.client_name)
    client = request.client
    name = client.client_name
    image_base_url = request.url.replace("/getAlbumInfo2", "/getCoverArt")
    image_base_url = image_base_url.replace(f"{res.id}", f"al-{res.id}")
    image_base_url = f"{image_base_url}?&id=al-{res.id}"
    info['smallImageUrl'] = f"{image_base_url}&input_size=small"
    info['mediumImageUrl'] = f"{image_base_url}&input_size=medium"
    info['largeImageUrl'] = f"{image_base_url}&input_size=large"
    info['cover_art'] = f'{image_base_url}&input_size=large'
    return request.formatter("albumInfo", info)
    

@api_routing("/getSong")
def track_info():
    res = get_entity(Track)
    return request.formatter(
        "song", res.as_subsonic_child(request.user, request.client)
    )


# getSimilarSongs
@api_routing("/getSimilarSongs")
def similar_songs():
    res = get_entity(Track)
    genre = res.genre
    if not genre:
        # 返回相同歌手的歌曲
        all_tracks = Track.select().where(Track.id != res.id, Track.artist == res.artist)
        similar_songs = [t for t in all_tracks][:10]
        return request.formatter(
            "similarSongs",
            {
                "song": [
                    t.as_subsonic_child(request.user, request.client) for t in similar_songs
                ]
            },
        )

    all_tracks = Track.select().where(Track.id != res.id)
    similar_songs_num = 10
    similar_songs = []
    similar_songs_genre = []
    similar_songs_partial_genre = []
    similar_songs_artist = []
    for t in all_tracks:
        if t.genre and genre:
            if t.genre == genre:
                similar_songs_genre.append(t)
            if genre.lower() in ((t.genre.lower())):
                similar_songs_partial_genre.append(t)
        if t.artist == res.artist:
            similar_songs_artist.append(t)
    #  优先选择相同流派的歌曲
    for song in similar_songs_genre:
        if len(similar_songs) < similar_songs_num:
            similar_songs.append(song)
    # 如果不够，再选择部分匹配流派的歌曲
    for song in similar_songs_partial_genre:
        if len(similar_songs) < similar_songs_num and song not in similar_songs:
            similar_songs.append(song)
    # 如果还不够，再选择相同艺人的歌曲
    for song in similar_songs_artist:
        if len(similar_songs) < similar_songs_num and song not in similar_songs:
            similar_songs.append(song)
    return request.formatter(
        "similarSongs",
        {
            "song": [
                t.as_subsonic_child(request.user, request.client) for t in similar_songs
            ]
        },
    )
