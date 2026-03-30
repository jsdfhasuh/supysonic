from datetime import datetime

from ..db import Track


def resolveTrackArtists(scanner, nfo_data, track_data, fallback_artists):
    track_artists = []
    for nfo_track in nfo_data.get("album", {}).get("track", []):
        try:
            nfo_track_number = int(nfo_track.get("cdnum", 1))
            nfo_track_disc = int(nfo_track.get("cdnum", 1))
        except Exception:
            nfo_track_number = nfo_track.get("cdnum", 1)
            nfo_track_disc = nfo_track.get("cdnum", 1)
        if (
            nfo_track_disc == track_data["number"]
            and nfo_track_number == track_data["disc"]
        ):
            if "artist" in nfo_track:
                track_artists = nfo_track["artist"]
                break

    if not track_artists:
        track_artists = fallback_artists

    return track_artists, scanner._Scanner__find_artist(track_artists[0])


def createOrUpdateTrack(scanner, track, path, mtime, track_data, album, artist):
    if track is None:
        track_data["root_folder"] = scanner._Scanner__find_root_folder(path)
        track_data["folder"] = scanner._Scanner__find_folder(path)
        track_data["album"] = album
        track_data["artist"] = artist
        track_data["created"] = datetime.fromtimestamp(mtime)
        try:
            track = Track.create(**track_data)
            scanner._Scanner__stats.added.tracks += 1
        except ValueError:
            scanner._Scanner__stats.errors.append(path)
            return None
        return track

    if track.album.id != album.id:
        track_data["album"] = album
    if track.artist.id != artist.id:
        track_data["artist"] = artist

    try:
        for attr, value in track_data.items():
            setattr(track, attr, value)
        track.save()
    except ValueError:
        scanner._Scanner__stats.errors.append(path)
        return None

    return track
