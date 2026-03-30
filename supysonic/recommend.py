# this func is made for recommend music playlist, but it is not implemented yet

from .db import User, Artist, Album, Track, User_Play_Activity,random, Playlist
import time

def create_recommend_playlist(num_songs=50,user = None):
    today = time.strftime('%Y-%m-%d', time.gmtime())
    exist_users = User.select()
    if not exist_users:
        return None  # No users in the database, cannot create a playlist
    if user and user not in exist_users:
        return None  # Specified user is not in the database
    users_to_process = [user] if user else exist_users
    for user in users_to_process:
        name = user.name
        user_activities = User_Play_Activity.select().where(
            User_Play_Activity.user == user
        )
        # find today recommend playlist exist or not
        exist_playlist = Playlist.select().where(
            (Playlist.user == user) & (Playlist.name == f"{name}'s {today} recommend playlist")
        )
        if exist_playlist:
            continue  # Skip users who already have a recommended playlist for today

        songs = {}  # song_id: play_count
        for activity in user_activities:
            song_id = activity.track.id
            if song_id in songs:
                songs[song_id] += 1
            else:
                songs[song_id] = 1
        if not songs:
            continue

        song_ids = list(songs)
        all_listened_songs = Track.select().where(Track.id.in_(song_ids))
        genres = {}  # genre: total_play_count
        for song in all_listened_songs:
            genre = song.genre
            play_count = songs[song.id]
            if genre in genres:
                genres[genre] += play_count
            else:
                genres[genre] = play_count
        genres_song_num = (
            0.25 * num_songs
        )  # Number of songs to recommend from each genre
        genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)
        genre_song_all = []
        all_genre = genres[:3]
        for genre_name, _ in all_genre:  # Get top 3 genres
            genre_song = Track.select().where(Track.genre == genre_name)
            single_genre_song_num = (
                1 / len(all_genre) * genres_song_num
            )  # Number of songs to recommend from each genre
            for song in genre_song:
                if song.id in song_ids:
                    continue  # Skip songs the user has already listened to
                genre_song_all.append(song)
                single_genre_song_num -= 1
                if single_genre_song_num <= 0:
                    break
            else:
                continue
        artist = {} # artist_id: total_play_count
        for song in all_listened_songs:
            artist_id = song.artist.id
            play_count = songs[song.id]
            if artist_id in artist:
                artist[artist_id] += play_count
            else:
                artist[artist_id] = play_count
        artist = sorted(artist.items(), key=lambda x: x[1], reverse=True)
        all_artist = artist[:3]
        artist_song_all = []
        artist_song_num = 0.45 * num_songs
        for artist_id, _ in artist[:3]:  # Get top 3 artists
            artist_song = Track.select().where(Track.artist == artist_id)
            single_artist_song_num = (
                1 / len(all_artist) * artist_song_num
            )  # Number of songs to recommend from each artist
            for song in artist_song:
                if song.id in song_ids:
                    continue  # Skip songs the user has already listened to
                artist_song_all.append(song)
                single_artist_song_num -= 1
                if single_artist_song_num <= 0:
                    break
            else:
                continue
        random_song_num = num_songs - len(genre_song_all) - len(artist_song_all)
        random_songs = []
        all_random_songs = Track.select().order_by(random())
        for song in all_random_songs:
            if song.id in song_ids:
                continue  # Skip songs the user has already listened to
            random_songs.append(song)
            if len(random_songs) >= random_song_num:
                break
        recommend_songs = genre_song_all + artist_song_all + random_songs
        name = f"{name}'s {today} recommend playlist"
        playlist = Playlist.create(user=user, name=name)
        playlist.comment = f"recommend"
        for song in recommend_songs:
            playlist.add(song)
        playlist.save()
             