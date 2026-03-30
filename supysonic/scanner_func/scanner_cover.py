import os

import mediafile

from ..covers import find_cover_in_folder
from ..db import Album, Image, Track
from ..tool import download_image
from ..MusicBrainz import get_musicbrainz_album_image_info, search_musicbrainz_album


def collectAlbumsMissingCover(scanner):
    lost_cover_album = []
    for album in Album.select():
        if (
            Image.select()
            .where(Image.related_id == album.id, Image.image_type == "album")
            .exists()
        ):
            continue
        lost_cover_album.append(album)
        scanner._Scanner__stats.lost_covers_albums[album.name] = ""
        scanner._Scanner__stats.lost_covers.albums += 1
    return lost_cover_album


def markAlbumCoverRestored(scanner, album):
    scanner._Scanner__stats.lost_covers.albums -= 1
    scanner._Scanner__stats.lost_covers_albums.pop(album.name, None)


def repairAlbumCover(scanner, album, get_cover_interner=False, lfm=None, logger=None):
    track = Track.select().where(Track.album == album.id).first()
    scanner._Scanner__stats.lost_covers_albums[album.name] = os.path.dirname(track.path) if track else ""
    if track is None:
        return

    cover_file = find_cover_in_folder(path=os.path.dirname(track.path), album_name=album.name)
    if cover_file:
        image_path = os.path.join(os.path.dirname(track.path), cover_file.name)
        Image.get_or_create(image_type="album", related_id=album.id, path=image_path)
        markAlbumCoverRestored(scanner, album)
        return

    cover = mediafile.MediaFile(track.path).art
    if cover:
        image_path = os.path.join(
            scanner._Scanner__config.BASE['tempdatafolder'], "album", f"{album.name}.png"
        )
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, "wb") as f:
            f.write(cover)
        Image.create(image_type="album", related_id=album.id, path=image_path)
        markAlbumCoverRestored(scanner, album)
        return

    if get_cover_interner and not cover and lfm:
        dl_status = False
        album_artist_name = album.artist.get_artist_name()
        search_musicbrainz_album(artist_name=album_artist_name, album_name=album.name)
        lastfm_album = lfm.get_albuminfo(artist_name=album_artist_name, album_name=album.name)
        album_mbid = lastfm_album.get('album', {}).get('mbid', "")
        if album_mbid:
            musicbrainz_image_json = get_musicbrainz_album_image_info(mb_album_id=album_mbid)
            if musicbrainz_image_json:
                for image in musicbrainz_image_json.get('images', []):
                    if image.get('front', False):
                        dl_url = image['image']
                        image_path = download_image(
                            save_folder=os.path.dirname(track.path),
                            save_name="cover.png",
                            url=dl_url,
                            logger=logger,
                        )
                        if image_path:
                            Image.create(image_type="album", related_id=album.id, path=image_path)
                            if logger:
                                logger.info("download %s cover image", album.name)
                            markAlbumCoverRestored(scanner, album)
                            dl_status = True
                            break
                        if logger:
                            logger.error("Download image failed")
        if lastfm_album and not dl_status and lastfm_album['album']['image']:
            save_folder = os.path.dirname(track.path)
            for image in lastfm_album['album']['image']:
                if image['size'] not in ["large"]:
                    continue
                dl_url = image['#text']
                if not dl_url:
                    continue
                image_path = download_image(
                    save_folder=save_folder,
                    save_name="cover.png",
                    url=dl_url,
                    logger=logger,
                )
                if image_path:
                    Image.create(image_type="album", related_id=album.id, path=image_path)
                    if logger:
                        logger.info("download %s cover image", album.name)
                    markAlbumCoverRestored(scanner, album)
                    break
                if logger:
                    logger.error("Download image failed")
