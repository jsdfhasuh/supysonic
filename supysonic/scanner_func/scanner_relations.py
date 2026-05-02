"""Persist album-artist and track-artist relation rows during scanning."""

from __future__ import annotations

from peewee import IntegrityError
from typing import Iterable, List, Optional, Tuple, TYPE_CHECKING, Union

from ..db import Album, AlbumArtist, Artist, Track, TrackArtist
from .scanner_common import sanitizeString
from .scanner_lookup import findArtist
from .scanner_review_tasks import rememberNewAlbum

if TYPE_CHECKING:
    from ..scanner import Scanner

def _normalize_artist_names(scanner: Scanner, artists: Iterable[Optional[str]]) -> List[str]:
    artist_names = [sanitizeString(artist) for artist in artists]
    artist_names = [name for name in artist_names if name]
    if not artist_names:
        artist_names = ["unknown"]
    return artist_names


def recordAlbumArtists(
    scanner: Scanner,
    artists: Iterable[Optional[str]],
    album: str,
    main_artist: Optional[Union[Artist, str]] = None,
) -> Tuple[List[AlbumArtist], Album, Artist]:
    artist_names = _normalize_artist_names(scanner, artists)
    with Artist._meta.database.atomic():
        resolved_artists = [findArtist(scanner, name) for name in artist_names]

        if main_artist is None:
            main = resolved_artists[0]
        elif isinstance(main_artist, Artist):
            main = main_artist
        else:
            main = findArtist(scanner, main_artist)

        album_row, created = Album.get_or_create(name=album, artist=main)
        if created:
            scanner.stats().added.albums += 1
            rememberNewAlbum(scanner, album_row)

        relations = []
        for artist in resolved_artists:
            try:
                relation, _ = AlbumArtist.get_or_create(album_id=album_row, artist_id=artist)
            except IntegrityError:
                refreshed_artist = Artist.get_or_none(Artist.id == artist.id)
                if refreshed_artist is None:
                    refreshed_artist = findArtist(scanner, artist.name)
                relation, _ = AlbumArtist.get_or_create(
                    album_id=album_row,
                    artist_id=refreshed_artist,
                )
            relations.append(relation)
    return relations, album_row, resolved_artists[0]


def recordTrackArtists(
    scanner: Scanner,
    artists: Iterable[Optional[str]],
    track: Track,
) -> Tuple[List[TrackArtist], Artist]:
    artist_names = _normalize_artist_names(scanner, artists)
    resolved_artists = [findArtist(scanner, name) for name in artist_names]
    relations = []
    for artist in resolved_artists:
        try:
            relation, _ = TrackArtist.get_or_create(track_id=track, artist_id=artist)
        except IntegrityError:
            refreshed_artist = Artist.get_or_none(Artist.id == artist.id)
            if refreshed_artist is None:
                refreshed_artist = findArtist(scanner, artist.name)
            relation, _ = TrackArtist.get_or_create(
                track_id=track,
                artist_id=refreshed_artist,
            )
        relations.append(relation)
    return relations, resolved_artists[0]


def replaceTrackArtists(
    scanner: Scanner,
    artists: Iterable[Optional[str]],
    track: Track,
) -> Tuple[List[TrackArtist], Artist]:
    TrackArtist.delete().where(TrackArtist.track_id == track).execute()
    return recordTrackArtists(scanner, artists, track)
