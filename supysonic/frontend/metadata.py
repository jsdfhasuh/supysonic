import logging

from flask import flash, redirect, render_template, request, session, url_for
from flask import current_app
from functools import wraps

from ..db import ClientPrefs, User, Artist, Album, Track
from ..lastfm import LastFm
from ..listenbrainz import ListenBrainz
from ..managers.user import UserManager

from . import admin_only, frontend

logger = logging.getLogger(__name__)


@frontend.route("/metadata")
@admin_only
def metadata():
    return render_template("metadata.html")


@frontend.route("/artists", methods=["GET", "POST"])
@admin_only
def metadata_artists():
    if request.method == "POST":
        # change artist metadata,post json data like {"id":1,"name":"New Artist Name"}
        raw_data = request.get_json()
        action = raw_data.get("action")
        if action == "change_real_artist":
            artist_id = raw_data.get("id")
            old_artist = Artist.get_by_id(artist_id)
            new_name = raw_data.get("real_name")
            new_artist,status = Artist.get_or_create(name=new_name)
            # fill new_artist with old_artist's artist_info_json
            if status:  # only when new artist is created
                new_artist.artist_info_json = old_artist.artist_info_json
                new_artist.save()
                logger.info(f"new artist {new_artist.name} created with old artist {old_artist.name}'s artist_info_json")
            # update old_artist's album to new_artists
            # albums = set(res.albums)
            # albums |= {t.album for t in res.tracks}
            # albums |= {rel.album_id for rel in res.artist_albums}
            albums =old_artist.albums
            for album in albums:
                album.artist = new_artist
                album.save()
                logger.info(f"change album {album.name}'s artist to new artist {new_artist.name}")
            # update old_artist's track to new_artist
            tracks = old_artist.tracks
            for track in tracks:
                track.artist = new_artist
                track.save()
                logger.info(f"change track {track.title}'s artist to new artist {new_artist.name}")
            # finally, set old_artist's real_artist to new_artist
            artist_albums_relations = old_artist.artist_albums
            for rel in artist_albums_relations:
                rel.artist_id = new_artist
                rel.save()
                logger.info(f"change artist_album relation {rel.id}'s artist to new artist {new_artist.name}")
            old_artist.real_artist = new_artist
            old_artist.save()
            logger.info(f"change old artist's real_artist to new artist {new_artist.name}")
        return {"status": "success"}
        pass
    
        
    elif request.method == "GET":

        return render_template("metadata.html")