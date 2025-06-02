import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import requests



class MySpotify:
    def __init__(self,config,scope = "user-library-read"):
        if config["client_id"] is not None and config["client_secret"] is not None:
            self.SPOTIPY_CLIENT_SECRET = config["client_secret"]
            self.SPOTIPY_CLIENT_ID = config["client_id"]
            self.__enabled = True
        else:
            return False
        auth_manager = SpotifyClientCredentials(client_id=self.SPOTIPY_CLIENT_ID, client_secret=self.SPOTIPY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        self.sp = sp
    def get_artist_info(self, name):
        retry_count = 0
        while retry_count < 3:
            try:
                results = self.sp.search(q=name, type='artist', limit=5)
                if results:
                    return results
                if retry_count == 2:
                    print("Failed to get artist name after 3 attempts.")
                    return name
                retry_count += 1
            except requests.exceptions.SSLError:
                print("SSL error occurred. Retrying...")
                retry_count += 1
            except requests.exceptions.ReadTimeout:
                print("Read timeout occurred. Retrying...")
                retry_count += 1
    def get_album_info(self, name):
        retry_count = 0
        while retry_count < 3:
            try:
                results = self.sp.search(q=name, type='album')
                if results:
                    return results
                if retry_count == 2:
                    print("Failed to get album name after 3 attempts.")
                    return name
                retry_count += 1
            except requests.exceptions.SSLError:
                print("SSL error occurred. Retrying...")
                retry_count += 1
            except requests.exceptions.ReadTimeout:
                print("Read timeout occurred. Retrying...")
                retry_count += 1