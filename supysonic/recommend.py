import logging
import time

from peewee import fn

from .db import Playlist, Track, User, User_Play_Activity


logger = logging.getLogger(__name__)

RECOMMENDED_PLAYLIST_COMMENT = "recommended"
LEGACY_RECOMMENDED_PLAYLIST_COMMENT = "recommend"
RECOMMENDED_PLAYLIST_COMMENTS = (
    RECOMMENDED_PLAYLIST_COMMENT,
    LEGACY_RECOMMENDED_PLAYLIST_COMMENT,
)


def getRecommendationDay(currentTime=None):
    currentTime = time.localtime() if currentTime is None else currentTime
    return time.strftime("%Y-%m-%d", currentTime)


def getRecommendPlaylistName(user, day=None):
    recommendationDay = getRecommendationDay() if day is None else day
    return f"{user.name}'s {recommendationDay} recommend playlist"


def getRecommendedPlaylistForDay(user, day=None):
    return (
        Playlist.select()
        .where((Playlist.user == user) & (Playlist.name == getRecommendPlaylistName(user, day)))
        .first()
    )


def getLatestRecommendedPlaylist(user):
    return (
        Playlist.select()
        .where(
            (Playlist.user == user)
            & (Playlist.comment.in_(RECOMMENDED_PLAYLIST_COMMENTS))
        )
        .order_by(Playlist.created.desc())
        .first()
    )


def _getUsersWithPlayActivity():
    return User.select().join(User_Play_Activity).distinct()


def _getUserTrackPlayCounts(user):
    query = (
        User_Play_Activity.select(
            User_Play_Activity.track_id.alias("track_id"),
            fn.COUNT(User_Play_Activity.id).alias("play_count"),
        )
        .where(User_Play_Activity.user == user)
        .group_by(User_Play_Activity.track_id)
    )
    return {row.track_id: row.play_count for row in query}


def _getTopGenresAndArtists(trackPlayCounts):
    genreCounts = {}
    artistCounts = {}
    if not trackPlayCounts:
        return [], []

    listenedTracks = Track.select(Track.id, Track.genre, Track.artist).where(
        Track.id.in_(list(trackPlayCounts.keys()))
    )
    for track in listenedTracks:
        playCount = trackPlayCounts.get(track.id, 0)
        if track.genre:
            genreCounts[track.genre] = genreCounts.get(track.genre, 0) + playCount
        artistCounts[track.artist_id] = artistCounts.get(track.artist_id, 0) + playCount

    topGenres = [
        genre for genre, _ in sorted(genreCounts.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    topArtists = [
        artistId for artistId, _ in sorted(artistCounts.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    return topGenres, topArtists


def _collectTracks(query, limit, excludedTrackIds):
    if limit <= 0:
        return []

    selectedTracks = []
    for track in query:
        if track.id in excludedTrackIds:
            continue
        selectedTracks.append(track)
        excludedTrackIds.add(track.id)
        if len(selectedTracks) >= limit:
            break
    return selectedTracks


def _buildRecommendedTracks(trackPlayCounts, numSongs):
    listenedTrackIds = set(trackPlayCounts.keys())
    excludedTrackIds = set(listenedTrackIds)
    recommendedTracks = []
    topGenres, topArtists = _getTopGenresAndArtists(trackPlayCounts)

    genreTarget = int(numSongs * 0.25)
    if topGenres and genreTarget > 0:
        perGenreLimit = max(1, genreTarget // len(topGenres))
        genreSelectedCount = 0
        for genreName in topGenres:
            remainingLimit = min(
                perGenreLimit,
                genreTarget - genreSelectedCount,
                numSongs - len(recommendedTracks),
            )
            if remainingLimit <= 0:
                break
            query = (
                Track.select()
                .where(Track.genre == genreName)
                .where(Track.id.not_in(list(listenedTrackIds)))
                .order_by(Track.play_count.desc(), Track.id)
            )
            selectedTracks = _collectTracks(query, remainingLimit, excludedTrackIds)
            genreSelectedCount += len(selectedTracks)
            recommendedTracks.extend(selectedTracks)

    artistTarget = int(numSongs * 0.45)
    if topArtists and artistTarget > 0:
        perArtistLimit = max(1, artistTarget // len(topArtists))
        artistSelectedCount = 0
        for artistId in topArtists:
            remainingLimit = min(
                perArtistLimit,
                artistTarget - artistSelectedCount,
                numSongs - len(recommendedTracks),
            )
            if remainingLimit <= 0:
                break
            query = (
                Track.select()
                .where(Track.artist == artistId)
                .where(Track.id.not_in(list(listenedTrackIds)))
                .order_by(Track.play_count.desc(), Track.id)
            )
            selectedTracks = _collectTracks(query, remainingLimit, excludedTrackIds)
            artistSelectedCount += len(selectedTracks)
            recommendedTracks.extend(selectedTracks)

    remaining = numSongs - len(recommendedTracks)
    if remaining > 0:
        query = (
            Track.select()
            .where(Track.id.not_in(list(listenedTrackIds)))
            .order_by(Track.play_count.desc(), Track.id)
        )
        recommendedTracks.extend(_collectTracks(query, remaining, excludedTrackIds))

    return recommendedTracks


def _setPlaylistTracks(playlist, tracks):
    uniqueTrackIds = []
    seenTrackIds = set()
    for track in tracks:
        trackId = str(track.id)
        if trackId in seenTrackIds:
            continue
        seenTrackIds.add(trackId)
        uniqueTrackIds.append(trackId)

    playlist.tracks = ",".join(uniqueTrackIds)


def _createRecommendPlaylistForUser(user, numSongs=50, day=None):
    if user is None:
        return None, False
    if User.get_or_none(User.id == user.id) is None:
        return None, False

    recommendationDay = getRecommendationDay() if day is None else day
    existingPlaylist = getRecommendedPlaylistForDay(user, recommendationDay)
    if existingPlaylist is not None:
        return existingPlaylist, False

    trackPlayCounts = _getUserTrackPlayCounts(user)
    if not trackPlayCounts:
        return None, False

    recommendedTracks = _buildRecommendedTracks(trackPlayCounts, numSongs)
    if not recommendedTracks:
        return None, False

    playlist = Playlist.create(
        user=user,
        name=getRecommendPlaylistName(user, recommendationDay),
        comment=RECOMMENDED_PLAYLIST_COMMENT,
    )
    _setPlaylistTracks(playlist, recommendedTracks)
    playlist.save()
    logger.info(
        "Created recommended playlist %s for %s with %d tracks",
        playlist.name,
        user.name,
        len(recommendedTracks),
    )
    return playlist, True


def refreshDailyRecommendPlaylists(num_songs=50, day=None):
    createdCount = 0
    recommendationDay = getRecommendationDay() if day is None else day
    for user in _getUsersWithPlayActivity():
        try:
            _, wasCreated = _createRecommendPlaylistForUser(
                user,
                numSongs=num_songs,
                day=recommendationDay,
            )
            if wasCreated:
                createdCount += 1
        except Exception:
            logger.exception(
                "Failed to create recommended playlist for user %s on %s",
                user.name,
                recommendationDay,
            )
    return createdCount


def create_recommend_playlist(num_songs=50, user=None, day=None):
    if user is not None:
        _, wasCreated = _createRecommendPlaylistForUser(user, numSongs=num_songs, day=day)
        return 1 if wasCreated else 0
    return refreshDailyRecommendPlaylists(num_songs=num_songs, day=day)
