"""Normalize and apply album-first external metadata enrichment."""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from ..MusicBrainz import get_musicbrainz_album, search_musicbrainz_album
from ..db import Album, Track, now
from ..discogs import DiscogsClient
from ..logging_utils import format_log_event

logger = logging.getLogger(__name__)

ENRICHMENT_ATTEMPTS_KEY = "enrichment_attempts"
STABLE_ENRICHMENT_ATTEMPT_STATUSES = {"matched", "empty", "skipped"}


def _normalize_list(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_release_type(value: object) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _extract_year(release_date: Optional[str]) -> Optional[str]:
    if not release_date:
        return None
    year = release_date.split("-", 1)[0]
    return year if re.match(r"^\d{4}$", year) else None


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "", [], {})}


def normalizeMusicBrainzAlbum(payload: Dict[str, Any]) -> Dict[str, Any]:
    release_date = str(payload.get("date") or "").strip() or None
    release_id = str(payload.get("id") or "").strip() or None
    release_group = payload.get("release-group") or {}
    release_type = _normalize_release_type(release_group.get("primary-type"))

    return _compact_dict(
        {
            "musicbrainz_id": release_id,
            "release_date": release_date,
            "year": _extract_year(release_date),
            "release_type": release_type,
            "providers_used": ["musicbrainz"] if payload else [],
            "source_urls": {
                "musicbrainz": f"https://musicbrainz.org/release/{release_id}"
            }
            if release_id
            else {},
        }
    )


def normalizeDiscogsAlbum(payload: Dict[str, Any]) -> Dict[str, Any]:
    genres = _normalize_list(payload.get("genres") or payload.get("genre"))
    styles = _normalize_list(payload.get("styles") or payload.get("style"))
    primary_genre = genres[0] if genres else styles[0] if styles else None
    discogs_id = str(payload.get("id") or "").strip() or None
    source_url = payload.get("uri") or payload.get("resource_url")

    return _compact_dict(
        {
            "discogs_id": discogs_id,
            "genres": genres,
            "styles": styles,
            "primary_genre": primary_genre,
            "providers_used": ["discogs"] if payload else [],
            "source_urls": {"discogs": source_url} if source_url else {},
        }
    )


def mergeAlbumEnrichment(
    musicbrainz_result: Optional[Dict[str, Any]],
    discogs_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    providers = []
    source_urls = {}

    for result in (musicbrainz_result or {}, discogs_result or {}):
        providers.extend(result.get("providers_used") or [])
        source_urls.update(result.get("source_urls") or {})
        for key, value in result.items():
            if key in ("providers_used", "source_urls"):
                continue
            if value not in (None, "", [], {}):
                merged[key] = value

    if providers:
        merged["providers_used"] = list(dict.fromkeys(providers))
    if source_urls:
        merged["source_urls"] = source_urls
    return merged


def _normalize_match_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def isAlbumMatchCandidate(
    artist_name: str,
    album_name: str,
    candidate_artist: str,
    candidate_album: str,
) -> bool:
    artist = _normalize_match_text(artist_name)
    album = _normalize_match_text(album_name)
    candidate_artist = _normalize_match_text(candidate_artist)
    candidate_album = _normalize_match_text(candidate_album)
    if not album or not candidate_album:
        return False
    album_matches = album == candidate_album or album in candidate_album or candidate_album in album
    if not artist or not candidate_artist:
        return album_matches
    artist_matches = (
        artist == candidate_artist
        or artist in candidate_artist
        or candidate_artist in artist
    )
    return album_matches and artist_matches


def _extractArtistNames(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        artist = value.get("artist")
        if isinstance(artist, dict):
            names = _extractArtistNames(artist)
            if names:
                return names

        for key in ("name", "artist", "anv"):
            name = value.get(key)
            if isinstance(name, str) and name.strip():
                return [name.strip()]
        return []
    if isinstance(value, Iterable):
        names = []
        for item in value:
            names.extend(_extractArtistNames(item))
        return names
    return []


def _extractMusicBrainzMatchFields(payload: Dict[str, Any]) -> tuple[str, str]:
    candidate_artist = " ".join(_extractArtistNames(payload.get("artist-credit")))
    candidate_album = str(payload.get("title") or "").strip()
    return candidate_artist, candidate_album


def _extractDiscogsMatchFields(payload: Dict[str, Any]) -> tuple[str, str]:
    candidate_artist = " ".join(
        _extractArtistNames(payload.get("artist") or payload.get("artists"))
    )
    candidate_album = str(
        payload.get("release_title") or payload.get("album") or ""
    ).strip()
    title = str(payload.get("title") or "").strip()

    if title:
        parts = re.split(r"\s+-\s+", title, 1)
        if len(parts) == 2:
            candidate_artist = candidate_artist or parts[0].strip()
            candidate_album = candidate_album or parts[1].strip()
        else:
            candidate_album = candidate_album or title

    return candidate_artist, candidate_album


def _extractProviderMatchFields(provider: str, payload: Dict[str, Any]) -> tuple[str, str]:
    if provider == "musicbrainz":
        return _extractMusicBrainzMatchFields(payload)
    return _extractDiscogsMatchFields(payload)


def _isProviderAlbumMatch(
    provider: str,
    artist_name: str,
    album_name: str,
    payload: Dict[str, Any],
) -> bool:
    if not payload:
        return False
    candidate_artist, candidate_album = _extractProviderMatchFields(provider, payload)
    return isAlbumMatchCandidate(
        artist_name,
        album_name,
        candidate_artist,
        candidate_album,
    )


class MusicBrainzClient:
    def search_album(self, artist_name: str, album_name: str) -> Dict[str, Any]:
        result = search_musicbrainz_album(artist_name=artist_name, album_name=album_name)
        release_id = result.get("id")
        if not release_id:
            return result
        details = get_musicbrainz_album(mb_album_id=release_id)
        return details or result


def getAlbumInfo(album: Album) -> Dict[str, Any]:
    if not album.album_info_json:
        return {}
    try:
        value = json.loads(album.album_info_json)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def setAlbumInfo(album: Album, info: Dict[str, Any]) -> None:
    album.album_info_json = json.dumps(info, ensure_ascii=False, sort_keys=True)


def _get_album_enrichment_attempts(album_info: Dict[str, Any]) -> Dict[str, Any]:
    attempts = album_info.get(ENRICHMENT_ATTEMPTS_KEY)
    return attempts if isinstance(attempts, dict) else {}


def _has_stable_provider_attempt(
    album_info: Dict[str, Any],
    provider: str,
    artist_name: str,
    album_name: str,
) -> bool:
    attempt = _get_album_enrichment_attempts(album_info).get(provider)
    if not isinstance(attempt, dict):
        return False
    if attempt.get("status") not in STABLE_ENRICHMENT_ATTEMPT_STATUSES:
        return False
    return attempt.get("artist") == artist_name and attempt.get("album") == album_name


def _record_provider_attempt(
    album: Album,
    provider: str,
    artist_name: str,
    status: str,
    reason: Optional[str] = None,
) -> None:
    album_info = getAlbumInfo(album)
    attempts = dict(_get_album_enrichment_attempts(album_info))
    attempt = {
        "status": status,
        "attempted_at": now().isoformat(),
        "artist": artist_name,
        "album": album.name,
    }
    if reason:
        attempt["reason"] = reason
    attempts[provider] = attempt
    album_info[ENRICHMENT_ATTEMPTS_KEY] = attempts
    setAlbumInfo(album, album_info)
    album.save()


def collectAlbumsNeedingEnrichment(discogs_enabled: bool = True) -> List[Album]:
    albums = []
    for album in Album.select():
        album_info = getAlbumInfo(album)
        artist_name = album.artist.get_artist_name()
        needs_musicbrainz = (
            not (album.year and album.release_date and album.release_type)
            and not _has_stable_provider_attempt(
                album_info,
                "musicbrainz",
                artist_name,
                album.name,
            )
        )
        needs_discogs = (
            discogs_enabled
            and not album_info.get("primary_genre")
            and not _has_stable_provider_attempt(
                album_info,
                "discogs",
                artist_name,
                album.name,
            )
        )
        if needs_musicbrainz or needs_discogs:
            albums.append(album)
    return albums


def _merge_info(existing: Dict[str, Any], enrichment: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key in (
        "musicbrainz_id",
        "discogs_id",
        "genres",
        "styles",
        "primary_genre",
        "source_urls",
        "providers_used",
    ):
        value = enrichment.get(key)
        if value in (None, "", [], {}):
            continue
        if key == "source_urls":
            current = dict(merged.get(key) or {})
            current.update(value)
            value = current
        elif key == "providers_used":
            value = list(dict.fromkeys(list(merged.get(key) or []) + list(value)))
        if merged.get(key) != value:
            merged[key] = value
            changes["album"].append("album_info_json")
    if changes["album"] or changes["tracks"]["year"] or changes["tracks"]["genre"]:
        merged["last_enriched_at"] = now().isoformat()
    return merged


def applyAlbumEnrichment(album: Album, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    changes = {"album": [], "tracks": {"year": [], "genre": []}}

    if not album.year and enrichment.get("year"):
        album.year = str(enrichment["year"])
        changes["album"].append("year")
    if not album.release_date and enrichment.get("release_date"):
        album.release_date = str(enrichment["release_date"])
        changes["album"].append("release_date")
    if not album.release_type and enrichment.get("release_type"):
        album.release_type = str(enrichment["release_type"])
        changes["album"].append("release_type")

    if enrichment.get("year"):
        for track in album.tracks.where(Track.year.is_null()):
            year = str(enrichment["year"])
            if year.isdigit():
                track.year = int(year)
                track.save()
                changes["tracks"]["year"].append(str(track.id))

    if enrichment.get("primary_genre"):
        for track in album.tracks.where(Track.genre.is_null()):
            track.genre = str(enrichment["primary_genre"])
            track.save()
            changes["tracks"]["genre"].append(str(track.id))

    album_info = _merge_info(getAlbumInfo(album), enrichment, changes)
    if album_info != getAlbumInfo(album):
        setAlbumInfo(album, album_info)

    if changes["album"] or changes["tracks"]["year"] or changes["tracks"]["genre"]:
        album.save()
    return changes


def _hasChanges(changes: Dict[str, Any]) -> bool:
    return bool(changes["album"] or changes["tracks"]["year"] or changes["tracks"]["genre"])


def _rememberEnrichedAlbum(scanner, album: Album) -> None:
    from .scanner_review_tasks import rememberExternalEnrichedAlbum

    rememberExternalEnrichedAlbum(scanner, album)


def _getChangedAlbumFields(changes: Dict[str, Any]) -> List[str]:
    return list(dict.fromkeys(changes["album"]))


def _getEnrichmentProviders(enrichment: Dict[str, Any]) -> List[str]:
    return list(enrichment.get("providers_used") or [])


def _logProviderResult(
    trace_logger: logging.Logger,
    provider: str,
    album: Album,
    artist_name: str,
    result: str,
    payload: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    error: Optional[Exception] = None,
) -> None:
    fields: Dict[str, Any] = {
        "provider": provider,
        "album_id": album.id,
        "artist": artist_name,
        "album": album.name,
        "result": result,
    }
    if payload:
        candidate_artist, candidate_album = _extractProviderMatchFields(provider, payload)
        fields["candidate_artist"] = candidate_artist or "-"
        fields["candidate_album"] = candidate_album or "-"
    if reason:
        fields["reason"] = reason
    if error:
        fields["error_type"] = error.__class__.__name__
        fields["error"] = str(error)

    message = format_log_event("scanner", "album_enrichment_provider_result", **fields)
    if result == "failed":
        trace_logger.warning(message)
    else:
        trace_logger.info(message)


def _logAlbumApplied(
    trace_logger: logging.Logger,
    album: Album,
    artist_name: str,
    enrichment: Dict[str, Any],
    changes: Dict[str, Any],
) -> None:
    trace_logger.info(
        format_log_event(
            "scanner",
            "album_enrichment_applied",
            album_id=album.id,
            artist=artist_name,
            album=album.name,
            providers=_getEnrichmentProviders(enrichment),
            changed_album_fields=_getChangedAlbumFields(changes),
            changed_track_year_count=len(changes["tracks"]["year"]),
            changed_track_genre_count=len(changes["tracks"]["genre"]),
        )
    )


def _logAlbumNoChange(
    trace_logger: logging.Logger,
    album: Album,
    artist_name: str,
    enrichment: Dict[str, Any],
) -> None:
    trace_logger.info(
        format_log_event(
            "scanner",
            "album_enrichment_no_change",
            album_id=album.id,
            artist=artist_name,
            album=album.name,
            providers=_getEnrichmentProviders(enrichment),
        )
    )


def _logAlbumFailure(
    trace_logger: logging.Logger,
    album: Album,
    error: Exception,
) -> None:
    trace_logger.warning(
        format_log_event(
            "scanner",
            "album_enrichment_album_failed",
            album_id=album.id,
            album=album.name,
            error_type=error.__class__.__name__,
            error=str(error),
        )
    )


def _isDiscogsEnabled(trace_logger: logging.Logger, discogs_client) -> bool:
    if not discogs_client:
        return False
    try:
        return bool(discogs_client.is_enabled())
    except Exception as exc:
        trace_logger.warning(
            format_log_event(
                "scanner",
                "album_enrichment_provider_result",
                provider="discogs",
                album_id="-",
                artist="-",
                album="-",
                result="failed",
                reason="enabled_check_failed",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
        )
        return False


def runAlbumEnrichmentPass(
    scanner,
    albums: Optional[Iterable[Album]] = None,
    musicbrainz_client=None,
    discogs_client=None,
    logger: Optional[logging.Logger] = None,
) -> None:
    trace_logger = logger or globals()["logger"]
    musicbrainz_client = musicbrainz_client or MusicBrainzClient()
    if discogs_client is None and hasattr(scanner, "scan_config"):
        discogs_client = DiscogsClient(getattr(scanner.scan_config, "DISCOGS", {}))
    discogs_enabled = _isDiscogsEnabled(trace_logger, discogs_client)
    album_list = (
        list(albums)
        if albums is not None
        else collectAlbumsNeedingEnrichment(discogs_enabled=discogs_enabled)
    )
    processed = 0
    matched = 0
    applied = 0
    skipped = 0
    failed = 0

    trace_logger.info(
        format_log_event(
            "scanner",
            "album_enrichment_pass_start",
            total_albums=len(album_list),
            discogs_enabled=discogs_enabled,
        )
    )

    for album in album_list:
        try:
            processed += 1
            artist_name = album.artist.get_artist_name()
            musicbrainz_result = {}
            discogs_result = {}

            if not _has_stable_provider_attempt(
                getAlbumInfo(album),
                "musicbrainz",
                artist_name,
                album.name,
            ):
                try:
                    musicbrainz_payload = musicbrainz_client.search_album(
                        artist_name,
                        album.name,
                    )
                    if _isProviderAlbumMatch(
                        "musicbrainz",
                        artist_name,
                        album.name,
                        musicbrainz_payload,
                    ):
                        _logProviderResult(
                            trace_logger,
                            "musicbrainz",
                            album,
                            artist_name,
                            "matched",
                            musicbrainz_payload,
                        )
                        _record_provider_attempt(
                            album,
                            "musicbrainz",
                            artist_name,
                            "matched",
                        )
                        musicbrainz_result = normalizeMusicBrainzAlbum(
                            musicbrainz_payload,
                        )
                    elif musicbrainz_payload:
                        _logProviderResult(
                            trace_logger,
                            "musicbrainz",
                            album,
                            artist_name,
                            "skipped",
                            musicbrainz_payload,
                            reason="candidate_mismatch",
                        )
                        _record_provider_attempt(
                            album,
                            "musicbrainz",
                            artist_name,
                            "skipped",
                            reason="candidate_mismatch",
                        )
                    else:
                        _logProviderResult(
                            trace_logger,
                            "musicbrainz",
                            album,
                            artist_name,
                            "empty",
                            reason="no_result",
                        )
                        _record_provider_attempt(
                            album,
                            "musicbrainz",
                            artist_name,
                            "empty",
                            reason="no_result",
                        )
                except Exception as exc:
                    _logProviderResult(
                        trace_logger,
                        "musicbrainz",
                        album,
                        artist_name,
                        "failed",
                        reason="provider_error",
                        error=exc,
                    )
                    _record_provider_attempt(
                        album,
                        "musicbrainz",
                        artist_name,
                        "failed",
                        reason="provider_error",
                    )

            if discogs_enabled and not _has_stable_provider_attempt(
                getAlbumInfo(album),
                "discogs",
                artist_name,
                album.name,
            ):
                try:
                    discogs_payload = discogs_client.search_album(artist_name, album.name)
                    if _isProviderAlbumMatch(
                        "discogs",
                        artist_name,
                        album.name,
                        discogs_payload,
                    ):
                        _logProviderResult(
                            trace_logger,
                            "discogs",
                            album,
                            artist_name,
                            "matched",
                            discogs_payload,
                        )
                        _record_provider_attempt(
                            album,
                            "discogs",
                            artist_name,
                            "matched",
                        )
                        discogs_result = normalizeDiscogsAlbum(discogs_payload)
                    elif discogs_payload:
                        _logProviderResult(
                            trace_logger,
                            "discogs",
                            album,
                            artist_name,
                            "skipped",
                            discogs_payload,
                            reason="candidate_mismatch",
                        )
                        _record_provider_attempt(
                            album,
                            "discogs",
                            artist_name,
                            "skipped",
                            reason="candidate_mismatch",
                        )
                    else:
                        _logProviderResult(
                            trace_logger,
                            "discogs",
                            album,
                            artist_name,
                            "empty",
                            reason="no_result",
                        )
                        _record_provider_attempt(
                            album,
                            "discogs",
                            artist_name,
                            "empty",
                            reason="no_result",
                        )
                except Exception as exc:
                    _logProviderResult(
                        trace_logger,
                        "discogs",
                        album,
                        artist_name,
                        "failed",
                        reason="provider_error",
                        error=exc,
                    )
                    _record_provider_attempt(
                        album,
                        "discogs",
                        artist_name,
                        "failed",
                        reason="provider_error",
                    )

            enrichment = mergeAlbumEnrichment(musicbrainz_result, discogs_result)
            if enrichment:
                matched += 1
            changes = applyAlbumEnrichment(
                album,
                enrichment,
            )
            if _hasChanges(changes):
                applied += 1
                _logAlbumApplied(trace_logger, album, artist_name, enrichment, changes)
                _rememberEnrichedAlbum(scanner, album)
            else:
                skipped += 1
                if enrichment:
                    _logAlbumNoChange(trace_logger, album, artist_name, enrichment)
        except Exception as exc:
            failed += 1
            _logAlbumFailure(trace_logger, album, exc)

    trace_logger.info(
        format_log_event(
            "scanner",
            "album_enrichment_pass_end",
            processed=processed,
            matched=matched,
            applied=applied,
            skipped=skipped,
            failed=failed,
        )
    )
