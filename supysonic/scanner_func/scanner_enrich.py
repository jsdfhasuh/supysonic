"""Fill missing album and artist metadata after the main scan finishes."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple, TYPE_CHECKING

from ..db import Album, Artist, Track, User
from ..lastfm import LastFm
from ..spotify import MySpotify
from ..tool import download_image, extract_year, read_dict_from_json, write_dict_to_json
from ..MusicBrainz import get_musicbrainz_album, search_musicbrainz_album
from .scanner_cover import collectAlbumsMissingCover, repairAlbumCover

if TYPE_CHECKING:
    from ..scanner import Scanner


def buildExternalMetadataClients(
    scanner: Scanner,
) -> Tuple[Optional[User], bool, Optional[LastFm], Optional[MySpotify]]:
    user = User.get_or_none(User.name == "root")
    if not (user and user.lastfm_status and scanner.scan_config.SPOTIFY['client_id']):
        return user, False, None, None
    return user, True, LastFm(scanner.scan_config.LASTFM, user), MySpotify(scanner.scan_config.SPOTIFY)


def collectAlbumsMissingYear(scanner: Scanner) -> List[Album]:
    lost_year_albums: List[Album] = []
    for album in Album.select():
        if album.year:
            continue
        track = Track.select().where(Track.album == album.id).first()
        lost_year_albums.append(album)
        scanner.stats().lost_year_albums[album.name] = os.path.dirname(track.path) if track else ""
    return lost_year_albums


def repairAlbumYear(
    scanner: Scanner,
    album: Album,
    lfm: Optional[LastFm] = None,
    sp: Optional[MySpotify] = None,
) -> bool:
    track = Track.select().where(Track.album == album.id).first()
    if track and track.year:
        album.year = extract_year(str(track.year))
    else:
        album_artist_name = album.artist.get_artist_name()
        musicbrainz_album = search_musicbrainz_album(artist_name=album_artist_name, album_name=album.name)
        if musicbrainz_album and musicbrainz_album.get('id'):
            result = get_musicbrainz_album(mb_album_id=musicbrainz_album['id'])
            year = extract_year(result.get('date'))
            if year:
                print(f"find year {year} for album {album.name}")
                album.year = year

    if album.year:
        album.save()
        scanner.stats().lost_year_albums.pop(album.name, None)
        return True

    if lfm and sp:
        album_artist_name = album.artist.get_artist_name()
        lastfm_album = lfm.get_albuminfo(artist_name=album_artist_name, album_name=album.name)
        if lastfm_album and 'wiki' in lastfm_album.get('album', {}):
            wiki_content = lastfm_album['album']['wiki'].get('summary', "")
            wiki_year = extract_year(s=lfm.get_wiki_year(wiki_content))
            if wiki_year:
                year = extract_year(wiki_year)
            else:
                published_year = lastfm_album['album']['wiki'].get('published', "")
                year = extract_year(published_year)
            print(f"find year {year} for album {album.name}")
            album.year = year
            album.save()
            scanner.stats().lost_year_albums.pop(album.name, None)
            return True
    return False


def collectArtistsMissingInfo(scanner: Scanner) -> List[Artist]:
    lost_cover_artist: List[Artist] = []
    for artist in Artist.select():
        if artist.artist_info_json:
            continue
        lost_cover_artist.append(artist)
        scanner.stats().lost_covers.artists += 1
        scanner.stats().lost_covers_artists.append(artist.get_artist_name())
    return lost_cover_artist


def repairArtistProfiles(
    scanner: Scanner,
    lost_cover_artist: List[Artist],
    get_cover_interner: bool = False,
    user: Optional[User] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    if not (get_cover_interner and user and user.lastfm_status and scanner.scan_config.SPOTIFY['client_id']):
        return

    sp = MySpotify(scanner.scan_config.SPOTIFY, user)
    lfm = LastFm(scanner.scan_config.LASTFM, user)
    for artist in lost_cover_artist:
        if artist.get_artist_name() == "Various Artists" or len(artist.get_artist_name()) < 2:
            continue
        result = lfm.get_artistinfo(
            name=artist.get_artist_name(),
            lang=scanner.scan_config.LASTFM['display_lang'],
        )
        if not result or result.get('message', "") == 'The artist you supplied could not be found':
            continue
        result_json = {"image": {}, "similarArtists": []}
        wiki_url = result['artist']['bio']['links']['link']['href']
        artist_name = result['artist']['name']
        artists_folder = os.path.join(scanner.scan_config.BASE['tempdatafolder'], 'artist', f'{artist_name}')
        sp_result = sp.get_artist_info(artist.name)
        os.makedirs(artists_folder, exist_ok=True)
        dl_status = False
        if sp_result:
            dl_status = True
            if sp_result['artists']['items']:
                for element in sp_result['artists']['items'][0]['images']:
                    size_num = element['height']
                    if size_num > 600:
                        size = "large"
                    elif 600 > size_num > 300:
                        size = "medium"
                    else:
                        size = "small"
                    dl_url = element['url']
                    image_path = download_image(
                        save_folder=artists_folder,
                        save_name=size,
                        url=dl_url,
                        logger=logger,
                    )
                    if image_path:
                        result_json['image'][size] = image_path
                        scanner.stats().lost_covers.artists -= 1
                    else:
                        if logger:
                            logger.error("Download image failed")
                        dl_status = False
            else:
                continue
        elif not dl_status:
            if logger:
                logger.error("Download image failed")
            continue

        wiki_content = lfm.get_lastfm_wiki(wiki_url)
        wiki_content = wiki_content if wiki_content else wiki_url
        if not wiki_content:
            if logger:
                logger.error("Get wiki content failed")
            continue
        result_json['biography'] = wiki_content
        result_json['lastFmUrl'] = result['artist']['url']
        write_dict_to_json(data=result_json, filename=os.path.join(artists_folder, "info.json"))
        info_path = os.path.join(artists_folder, "info.json")
        if os.path.exists(info_path):
            artist.artist_info_json = info_path
            artist.save()
            scanner.stats().lost_covers_artists.remove(artist.name)


def repairMissingArtistImages(
    scanner: Scanner,
    get_cover_interner: bool = False,
    user: Optional[User] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    if not (get_cover_interner and user and user.lastfm_status and scanner.scan_config.SPOTIFY['client_id']):
        return

    sp = MySpotify(scanner.scan_config.SPOTIFY, user)
    for artist in Artist.select().where(Artist.artist_info_json.is_null(False)):
        if not os.path.exists(artist.artist_info_json):
            continue
        info = read_dict_from_json(artist.artist_info_json)
        if not info or not info.get('image'):
            continue
        for size, image_path in info['image'].items():
            if os.path.exists(image_path):
                continue
            sp_result = sp.get_artist_info(artist.name)
            artists_folder = os.path.dirname(image_path)
            if sp_result and sp_result['artists']['items']:
                for element in sp_result['artists']['items'][0]['images']:
                    size_num = element['height']
                    if size_num > 600:
                        size = "large"
                    elif 600 > size_num > 300:
                        size = "medium"
                    else:
                        size = "small"
                    dl_url = element['url']
                    if download_image(
                        save_folder=artists_folder,
                        save_name=size,
                        url=dl_url,
                        logger=logger,
                    ):
                        info['image'][size] = os.path.join(artists_folder, f"{size}.png")
                        write_dict_to_json(
                            data=info,
                            filename=os.path.join(artists_folder, "info.json"),
                        )


def findLostInformation(scanner: Scanner, logger: Optional[logging.Logger] = None) -> None:
    user, get_cover_interner, lfm, sp = buildExternalMetadataClients(scanner)

    for album in list(collectAlbumsMissingYear(scanner)):
        repairAlbumYear(scanner, album, lfm=lfm, sp=sp)

    for album in collectAlbumsMissingCover(scanner):
        repairAlbumCover(scanner, album, get_cover_interner=get_cover_interner, lfm=lfm, logger=logger)

    lost_cover_artist = collectArtistsMissingInfo(scanner)
    repairArtistProfiles(scanner, lost_cover_artist, get_cover_interner=get_cover_interner, user=user, logger=logger)
    repairMissingArtistImages(scanner, get_cover_interner=get_cover_interner, user=user, logger=logger)
