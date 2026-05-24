import logging
import os
import re
import time

from datetime import datetime, timedelta
from peewee import fn
from typing import Optional

from .config import DefaultConfig
from .db import Playlist, Track, User, User_Play_Activity
from .recommendation_feedback import get_disliked_recommended_song_ids
from .tool import write_dict_to_json


logger = logging.getLogger(__name__)

RECOMMENDED_PLAYLIST_COMMENT = "recommended"
LEGACY_RECOMMENDED_PLAYLIST_COMMENT = "recommend"
RECOMMENDED_PLAYLIST_COMMENTS = (
    RECOMMENDED_PLAYLIST_COMMENT,
    LEGACY_RECOMMENDED_PLAYLIST_COMMENT,
)
RECOMMENDED_PLAYLIST_DAY_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
SAFE_ARCHIVE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._@-]+")
DEFAULT_RECOMMEND_PLAYLIST_RETENTION_DAYS = 5


def getRecommendationDay(currentTime=None) -> str:
    currentTime = time.localtime() if currentTime is None else currentTime
    return time.strftime("%Y-%m-%d", currentTime)


def getRecommendPlaylistName(user, day=None) -> str:
    recommendationDay = getRecommendationDay() if day is None else day
    return f"{user.name}'s {recommendationDay} recommend playlist"


def recommended_playlist_where():
    return Playlist.comment.in_(RECOMMENDED_PLAYLIST_COMMENTS)


def non_recommended_playlist_where():
    return Playlist.comment.is_null(True) | Playlist.comment.not_in(
        RECOMMENDED_PLAYLIST_COMMENTS
    )


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
        trackId = str(track.id)
        if trackId in excludedTrackIds:
            continue
        selectedTracks.append(track)
        excludedTrackIds.add(trackId)
        if len(selectedTracks) >= limit:
            break
    return selectedTracks


def _buildRecommendedTracks(trackPlayCounts, numSongs, excludedTrackIds=None):
    listenedTrackIds = set(trackPlayCounts.keys())
    selectedTrackIds = {str(trackId) for trackId in listenedTrackIds}
    if excludedTrackIds:
        selectedTrackIds.update(str(trackId) for trackId in excludedTrackIds)
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
            selectedTracks = _collectTracks(query, remainingLimit, selectedTrackIds)
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
            selectedTracks = _collectTracks(query, remainingLimit, selectedTrackIds)
            artistSelectedCount += len(selectedTracks)
            recommendedTracks.extend(selectedTracks)

    remaining = numSongs - len(recommendedTracks)
    if remaining > 0:
        query = (
            Track.select()
            .where(Track.id.not_in(list(listenedTrackIds)))
            .order_by(Track.play_count.desc(), Track.id)
        )
        recommendedTracks.extend(_collectTracks(query, remaining, selectedTrackIds))

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


def _get_recommend_playlist_retention_days(config: Optional[object] = None) -> int:
    daemonConfig = getattr(config, "DAEMON", None)
    retentionDays = DEFAULT_RECOMMEND_PLAYLIST_RETENTION_DAYS
    if isinstance(daemonConfig, dict):
        retentionDays = daemonConfig.get(
            "recommend_playlist_retention_days", retentionDays
        )

    try:
        retentionDays = int(retentionDays)
    except (TypeError, ValueError):
        retentionDays = DEFAULT_RECOMMEND_PLAYLIST_RETENTION_DAYS

    return max(1, retentionDays)


def _recommend_playlist_archive_enabled(config: Optional[object] = None) -> bool:
    daemonConfig = getattr(config, "DAEMON", None)
    if isinstance(daemonConfig, dict):
        return bool(daemonConfig.get("recommend_playlist_archive_enabled", True))
    return True


def _get_recommend_playlist_archive_root(config: Optional[object] = None) -> str:
    webappConfig = getattr(config, "WEBAPP", None)
    cacheDir = DefaultConfig.WEBAPP["cache_dir"]
    if isinstance(webappConfig, dict) and webappConfig.get("cache_dir"):
        cacheDir = webappConfig["cache_dir"]
    return os.path.join(cacheDir, "recommend-playlists")


def _parse_recommendation_date(dayText):
    try:
        return datetime.strptime(dayText, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _get_recommendation_date_for_playlist(playlist):
    match = RECOMMENDED_PLAYLIST_DAY_RE.search(playlist.name or "")
    if match is not None:
        parsedDate = _parse_recommendation_date(match.group(1))
        if parsedDate is not None:
            return parsedDate

    created = getattr(playlist, "created", None)
    if created is not None and hasattr(created, "date"):
        return created.date()

    return _parse_recommendation_date(getRecommendationDay())


def _serialize_recommend_playlist_track(track):
    return {
        "id": str(track.id),
        "title": track.title,
        "artist": track.artist.name if track.artist else "",
        "album": track.album.name if track.album else "",
        "duration": track.duration,
        "path": track.path,
    }


def _safe_archive_segment(value, fallback) -> str:
    segment = SAFE_ARCHIVE_SEGMENT_RE.sub("_", str(value or "")).strip("._")
    if not segment:
        segment = str(fallback)
    return segment[:128]


def _build_recommend_playlist_archive_path(playlist, archiveRoot):
    recommendationDate = _get_recommendation_date_for_playlist(playlist)
    recommendationDay = recommendationDate.isoformat()
    userDir = os.path.join(
        archiveRoot,
        _safe_archive_segment(playlist.user.name, playlist.user.id),
    )
    archivePath = os.path.join(userDir, f"{recommendationDay}.json")
    if os.path.exists(archivePath):
        archivePath = os.path.join(userDir, f"{recommendationDay}_{playlist.id}.json")
    return archivePath, recommendationDay


def _archive_recommended_playlist(playlist, archiveRoot):
    tracks = playlist.get_tracks()
    archivePath, recommendationDay = _build_recommend_playlist_archive_path(
        playlist, archiveRoot
    )
    payload = {
        "playlist_id": str(playlist.id),
        "user": playlist.user.name,
        "name": playlist.name,
        "comment": playlist.comment,
        "created": playlist.created.isoformat() if playlist.created else None,
        "archived_at": datetime.utcnow().isoformat(),
        "recommendation_day": recommendationDay,
        "track_ids": [str(track.id) for track in tracks],
        "tracks": [_serialize_recommend_playlist_track(track) for track in tracks],
    }
    write_dict_to_json(payload, archivePath)
    return archivePath


def _archive_old_recommended_playlists_for_user(
    user, currentDay, config: Optional[object] = None
) -> int:
    if not _recommend_playlist_archive_enabled(config):
        return 0

    currentDate = _parse_recommendation_date(currentDay) or _parse_recommendation_date(
        getRecommendationDay()
    )
    retentionDays = _get_recommend_playlist_retention_days(config)
    cutoffDate = currentDate - timedelta(days=retentionDays - 1)
    archiveRoot = _get_recommend_playlist_archive_root(config)
    archivedCount = 0

    query = (
        Playlist.select()
        .where((Playlist.user == user) & recommended_playlist_where())
        .order_by(Playlist.created.asc(), Playlist.id.asc())
    )
    for playlist in query:
        playlistDate = _get_recommendation_date_for_playlist(playlist)
        if playlistDate is None or playlistDate >= cutoffDate:
            continue

        try:
            archivePath = _archive_recommended_playlist(playlist, archiveRoot)
        except Exception:
            logger.exception(
                "Failed to archive recommended playlist %s for %s",
                playlist.id,
                user.name,
            )
            continue

        playlist.delete_instance()
        archivedCount += 1
        logger.info(
            "Archived recommended playlist %s for %s to %s",
            playlist.name,
            user.name,
            archivePath,
        )

    return archivedCount


def _createRecommendPlaylistForUser(
    user, numSongs=50, day=None, config: Optional[object] = None
):
    if user is None:
        return None, False
    if User.get_or_none(User.id == user.id) is None:
        return None, False

    recommendationDay = getRecommendationDay() if day is None else day
    _archive_old_recommended_playlists_for_user(
        user, recommendationDay, config=config
    )
    existingPlaylist = getRecommendedPlaylistForDay(user, recommendationDay)
    if existingPlaylist is not None:
        return existingPlaylist, False

    trackPlayCounts = _getUserTrackPlayCounts(user)
    if not trackPlayCounts:
        return None, False

    dislikedTrackIds = get_disliked_recommended_song_ids(user)
    recommendedTracks = _buildRecommendedTracks(
        trackPlayCounts,
        numSongs,
        excludedTrackIds=dislikedTrackIds,
    )
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


def refreshDailyRecommendPlaylists(
    num_songs=50, day=None, config: Optional[object] = None
) -> int:
    createdCount = 0
    recommendationDay = getRecommendationDay() if day is None else day
    for user in _getUsersWithPlayActivity():
        try:
            _, wasCreated = _createRecommendPlaylistForUser(
                user,
                numSongs=num_songs,
                day=recommendationDay,
                config=config,
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


def create_recommend_playlist(
    num_songs=50, user=None, day=None, config: Optional[object] = None
) -> int:
    if user is not None:
        _, wasCreated = _createRecommendPlaylistForUser(
            user,
            numSongs=num_songs,
            day=day,
            config=config,
        )
        return 1 if wasCreated else 0
    return refreshDailyRecommendPlaylists(
        num_songs=num_songs, day=day, config=config
    )
