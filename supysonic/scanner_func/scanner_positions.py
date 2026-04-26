"""Repair album and track artist position ordering after scanning completes."""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from ..db import Album, AlbumArtist, Artist, TrackArtist

if TYPE_CHECKING:
    from ..scanner import Scanner

def _album_artist_exists_in_tracks(album: Album, artist: Artist) -> bool:
    for track in album.tracks:
        if (
            TrackArtist.select()
            .where(
                (TrackArtist.track_id == track)
                & (TrackArtist.artist_id == artist)
            )
            .exists()
        ):
            return True
    return False


def _remove_invalid_album_artist_relations() -> None:
    relations = AlbumArtist.select().where(AlbumArtist.position == 0)
    for relation in relations:
        album = relation.album_id
        artist = relation.artist_id
        if not _album_artist_exists_in_tracks(album, artist):
            relation.delete_instance()


def _get_albums_needing_position_repair() -> List[Album]:
    albums = []
    seen_album_ids = set()
    for relation in AlbumArtist.select().where(AlbumArtist.position == 0):
        album = relation.album_id
        if album.id in seen_album_ids:
            continue
        seen_album_ids.add(album.id)
        albums.append(album)
    return albums


def _count_album_track_artists(album: Album) -> List[Tuple[Artist, int]]:
    artist_count = {}
    for track in album.tracks:
        for track_artist in track.track_artists:
            artist = track_artist.artist_id
            if artist not in artist_count:
                artist_count[artist] = 0
            artist_count[artist] += 1
    return sorted(artist_count.items(), key=lambda item: item[1], reverse=True)


def _apply_album_artist_positions(album: Album, sorted_artists: List[Tuple[Artist, int]]) -> None:
    for position, element in enumerate(sorted_artists, start=1):
        artist = element[0]
        if position == 1:
            album.artist = artist
            album.save()

        relation = AlbumArtist.get_or_none(album_id=album, artist_id=artist)
        if relation is None:
            continue
        relation.position = position
        relation.save()

        if position == 1:
            for track in album.tracks:
                track.artist = artist
                track.save()

        for track_relation in artist.artist_tracks:
            if track_relation.track_id.album == album:
                track_relation.position = position
                track_relation.save()


def decideAllPositions(scanner: Scanner) -> None:
    # Keep the scanner argument so Scanner can delegate to a consistent
    # helper interface even though this repair step currently only needs DB state.
    _remove_invalid_album_artist_relations()
    for album in _get_albums_needing_position_repair():
        sorted_artists = _count_album_track_artists(album)
        _apply_album_artist_positions(album, sorted_artists)
