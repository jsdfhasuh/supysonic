import json
import mimetypes
import os.path

from peewee import fn


def serialize_folder_child(folder, user):
    from .annotations import RatingFolder, StarredFolder

    info = {
        "id": str(folder.id),
        "isDir": True,
        "title": folder.name,
        "album": folder.name,
        "created": folder.created.isoformat(),
    }
    if not folder.root:
        info["parent"] = str(folder.parent.id)
        info["artist"] = folder.parent.name
    if folder.cover_art:
        info["coverArt"] = str(folder.id)
    else:
        for track in folder.tracks:
            if track.has_art:
                info["coverArt"] = str(track.id)
                break

    try:
        starred = StarredFolder[user.id, folder.id]
        info["starred"] = starred.date.isoformat()
    except StarredFolder.DoesNotExist:
        pass

    try:
        rating = RatingFolder[user.id, folder.id]
        info["userRating"] = rating.rating
    except RatingFolder.DoesNotExist:
        pass

    avgRating = (
        RatingFolder.select(fn.avg(RatingFolder.rating, coerce=False))
        .where(RatingFolder.rated == folder)
        .scalar()
    )
    if avgRating:
        info["averageRating"] = avgRating

    return info


def serialize_folder_artist(folder, user):
    from .annotations import StarredFolder

    info = {"id": str(folder.id), "name": folder.name}

    try:
        starred = StarredFolder[user.id, folder.id]
        info["starred"] = starred.date.isoformat()
    except StarredFolder.DoesNotExist:
        pass

    return info


def serialize_folder_directory(folder, user, client):
    from .library import Folder

    info = {
        "id": str(folder.id),
        "name": folder.name,
        "child": [
            f.as_subsonic_child(user)
            for f in folder.children.order_by(fn.lower(Folder.name))
        ]
        + [
            t.as_subsonic_child(user, client)
            for t in sorted(folder.tracks, key=lambda t: t.sort_key())
        ],
    }
    if not folder.root:
        info["parent"] = str(folder.parent.id)

    return info


def serialize_artist(artist, user):
    from .annotations import StarredArtist
    from .library import Album, AlbumArtist

    album_count = (
        Album.select()
        .distinct()
        .join(
            AlbumArtist,
            join_type="LEFT OUTER JOIN",
            on=(Album.id == AlbumArtist.album_id),
        )
        .where(
            (Album.artist == artist)
            | (AlbumArtist.artist_id == artist)
        )
        .count()
    )

    info = {
        "id": str(artist.id),
        "name": artist.name,
        "coverArt": "ar-" + str(artist.id),
        "albumCount": album_count,
    }

    try:
        starred = StarredArtist[user.id, artist.id]
        info["starred"] = starred.date.isoformat()
    except StarredArtist.DoesNotExist:
        pass
    return info


def serialize_album(album, user, server_type=None):
    from .annotations import StarredAlbum
    from .library import Folder, Track

    server_name = (server_type or "").lower()
    is_music_client = "music" in server_name
    duration, created = album.tracks.select(
        fn.sum(Track.duration), fn.min(Track.created)
    ).scalar(as_tuple=True)
    all_artists = album.get_all_artists()
    info = {
        "id": str(album.id),
        "name": str(album.name),
        "artist": str(album.artist.get_artist_name()),
        "artistId": str(album.artist.id),
        "songCount": album.tracks.count(),
        "duration": duration,
        "created": created.isoformat(),
    }

    if is_music_client:
        info["albumArtist"] = str(album.artist.get_artist_name())
        info["albumArtistId"] = str(album.artist.id)
        info["smallImageUrl"] = ""
        info["mediumImageUrl"] = ""
        info["largeImageUrl"] = ""
        participants = {"albumartist": [], "artist": []}

        for artist in all_artists:
            participants["artist"].append(
                {"id": str(artist.id), "name": str(artist.get_artist_name())}
            )
        info["participants"] = participants
        info["coverArt"] = "al-" + str(album.id)
    else:
        track_with_cover = (
            album.tracks.join(Folder).where(Folder.cover_art.is_null(False)).first()
        )
        if track_with_cover is not None:
            info["coverArt"] = str(track_with_cover.folder.id)
        else:
            track_with_cover = album.tracks.where(Track.has_art).first()
            if track_with_cover is not None:
                info["coverArt"] = str(track_with_cover.id)
    if album.year:
        info["year"] = album.year

    album_info = {}
    if album.album_info_json:
        try:
            album_info_value = json.loads(album.album_info_json)
        except (TypeError, ValueError):
            album_info_value = {}
        if isinstance(album_info_value, dict):
            album_info = album_info_value

    if is_music_client:
        if album.release_date:
            info["releaseDate"] = album.release_date
        if album.release_type:
            info["releaseType"] = album.release_type

        styles = album_info.get("styles")
        if isinstance(styles, list) and styles:
            info["styles"] = [str(style) for style in styles if style]

        musicbrainz_id = album_info.get("musicbrainz_id")
        if musicbrainz_id:
            info["musicBrainzId"] = str(musicbrainz_id)

        discogs_id = album_info.get("discogs_id")
        if discogs_id:
            info["discogsId"] = str(discogs_id)

    genre = ", ".join(
        g
        for (g,) in album.tracks.select(Track.genre)
        .where(Track.genre.is_null(False))
        .distinct()
        .tuples()
    )
    if genre:
        info["genre"] = genre

    try:
        starred = StarredAlbum[user.id, album.id]
        info["starred"] = starred.date.isoformat()
    except StarredAlbum.DoesNotExist:
        pass

    return info


def serialize_track_child(track, user, prefs):
    from .annotations import RatingTrack, StarredTrack

    info = {
        "id": str(track.id),
        "parent": str(track.folder.id),
        "isDir": False,
        "title": track.title,
        "album": track.album.name,
        "artist": track.artist.get_artist_name(),
        "track": track.number,
        "size": os.path.getsize(track.path) if os.path.isfile(track.path) else -1,
        "contentType": track.mimetype,
        "suffix": track.suffix(),
        "duration": track.duration,
        "bitRate": track.bitrate,
        "path": track.path[len(track.root_folder.path) + 1 :],
        "isVideo": False,
        "discNumber": track.disc,
        "created": track.created.isoformat(),
        "albumId": str(track.album.id),
        "artistId": str(track.artist.id),
        "type": "music",
    }

    if track.year:
        info["year"] = track.year
    if track.genre:
        info["genre"] = track.genre
    if track.has_art:
        info["coverArt"] = str(track.id)
    elif track.folder.cover_art:
        info["coverArt"] = str(track.folder.id)

    try:
        starred = StarredTrack[user.id, track.id]
        info["starred"] = starred.date.isoformat()
    except StarredTrack.DoesNotExist:
        pass

    try:
        rating = RatingTrack[user.id, track.id]
        info["userRating"] = rating.rating
    except RatingTrack.DoesNotExist:
        pass

    avgRating = (
        RatingTrack.select(fn.avg(RatingTrack.rating, coerce=False))
        .where(RatingTrack.rated == track)
        .scalar()
    )
    if avgRating:
        info["averageRating"] = avgRating

    if (
        prefs is not None
        and prefs.format is not None
        and prefs.format != track.suffix()
    ):
        info["transcodedSuffix"] = prefs.format
        info["transcodedContentType"] = (
            mimetypes.guess_type("dummyname." + prefs.format, False)[0]
            or "application/octet-stream"
        )

    return info


def serialize_user(user):
    return {
        "username": user.name,
        "email": user.mail or "",
        "scrobblingEnabled": user.lastfm_session is not None and user.lastfm_status,
        "adminRole": user.admin,
        "settingsRole": True,
        "downloadRole": True,
        "uploadRole": False,
        "playlistRole": True,
        "coverArtRole": False,
        "commentRole": False,
        "podcastRole": False,
        "streamRole": True,
        "jukeboxRole": user.admin or user.jukebox,
        "shareRole": False,
    }


def serialize_chat_message(message):
    return {
        "username": message.user.name,
        "time": message.time * 1000,
        "message": message.message,
    }


def serialize_playlist(playlist, user, tracks=None):
    tracks = playlist.get_tracks() if tracks is None else tracks
    first_track = tracks[0] if tracks else None
    first_album = first_track.album if first_track else None
    info = {
        "id": str(playlist.id),
        "name": (
            playlist.name
            if playlist.user.id == user.id
            else f"[{playlist.user.name}] {playlist.name}"
        ),
        "owner": playlist.user.name,
        "public": playlist.public,
        "songCount": len(tracks),
        "duration": sum(t.duration for t in tracks),
        "created": playlist.created.isoformat(),
    }
    if first_album:
        info["coverArt"] = f"al-{first_album.id}"
    if playlist.comment:
        info["comment"] = playlist.comment
    return info


def serialize_radio_station(station):
    info = {
        "id": str(station.id),
        "streamUrl": station.stream_url,
        "name": station.name,
        "homePageUrl": station.homepage_url,
    }
    return info
