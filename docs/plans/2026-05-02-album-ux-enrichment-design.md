# Album UX Enrichment Design

**Updated:** 2026-05-09

**Goal:** Improve immediately visible album metadata quality by enriching albums from `MusicBrainz` by default and optional `Discogs`, writing only missing values into the main library, and exposing enriched data in review, web, and API surfaces.

**Confirmed Constraints**
- Scope is album-first, not artist-first or track-first.
- Prioritize fields with immediate UX impact over archival completeness.
- Write directly to the main library tables rather than a staging area.
- Only fill empty values; never overwrite existing metadata.
- Keep review tasks as post-write human verification, not as a gate before persistence.
- Do not require Discogs credentials for the feature to work.
- Do not depend on Discogs images in phase 1; use Discogs only for descriptive text metadata.

**Current State**
- Scan post-processing already runs through `Scanner.find_lost_information()` from both full scans and watcher batches.
- Current enrichment covers:
  - album year through track metadata, MusicBrainz, then Last.fm fallback
  - album cover through local file, embedded artwork, MusicBrainz cover art, then Last.fm fallback
  - artist biography / images through Last.fm and Spotify
- Existing UI and API already benefit directly from:
  - `coverArt`
  - `year`
  - `genre`
- Existing browsing and similarity behavior often depends on `Track.year` and `Track.genre`, not just album-level fields.

**Provider Strategy**
- `MusicBrainz` is the default structured provider.
  - It does not require a project-specific token.
  - It must use a meaningful User-Agent.
  - It provides release date, year, release type, MusicBrainz IDs, and source URLs.
- `Discogs` is an optional descriptive provider.
  - It is treated as free-to-use within API policy and rate limits, but not as a hard dependency.
  - It should be disabled by default until a token is configured.
  - It provides genres, styles, primary genre, Discogs IDs, and source URLs.
  - It must not block or fail the scan if credentials are missing or the API rate-limits requests.
- Existing Last.fm and Spotify behavior should remain in place for artist profile/image flows and legacy fallbacks.

**Chosen Scope For Phase 1**
- Enrich album-facing fields that users can notice immediately:
  - release date
  - year
  - release type
  - genres / styles
- Backfill empty track-level fields needed by current browsing behavior:
  - `Track.year`
  - `Track.genre`
- Keep cover repair on the current local/embedded/MusicBrainz/Last.fm flow; do not add Discogs cover download in this phase.

**Fields Explicitly Deferred**
- `label`
- `country`
- `catalog_number`
- marketplace data
- Discogs image download
- multi-provider confidence scoring
- normalized genre/style lookup tables

These are useful for completeness, but do not produce enough immediate UX lift for phase 1.

**Persistence Model**
- Add direct album fields for high-value structured data:
  - `Album.release_date`
  - `Album.release_type`
- Keep `Album.year` as the quick display / browse field.
- Add `Album.album_info_json` for extensible structured payloads such as:

```json
{
  "musicbrainz_id": "...",
  "discogs_id": "...",
  "genres": ["Rock"],
  "styles": ["Indie Rock"],
  "primary_genre": "Rock",
  "providers_used": ["musicbrainz", "discogs"],
  "source_urls": {
    "musicbrainz": "...",
    "discogs": "..."
  },
  "last_enriched_at": "2026-05-09T12:34:56",
  "field_updates": {
    "album": ["release_date", "release_type"],
    "tracks": ["year", "genre"]
  }
}
```

**Why `release_date` Is A String**
- MusicBrainz commonly returns partial dates such as `YYYY` or `YYYY-MM`.
- A strict date field would either reject partial values or require lossy coercion.
- Storing the raw normalized string preserves source fidelity.

**Schema Version**
- Current working tree has already moved schema version to `20260507` for client release metadata.
- Album enrichment must not reuse older plan version `20260503`.
- Use `20260509` for album enrichment migrations and update `SCHEMA_VERSION` to `20260509` when implementation starts.

**Configuration Model**
- Add a `MUSICBRAINZ` config section for request behavior:
  - `api_url`
  - `cover_art_api_url`
  - `user_agent`
  - `request_delay_seconds`
- Add a `DISCOGS` config section:
  - `enabled`
  - `api_url`
  - `token`
  - `user_agent`
  - `request_delay_seconds`
  - Real Discogs tokens must not be committed to source control.
- Defaults:
  - MusicBrainz enabled by default.
  - Discogs disabled unless `enabled = on` and `token` is non-empty.

**Enrichment Flow**
1. The existing scan/watcher completion flow enters `find_lost_information()`.
2. A new album UX enrichment pass runs after external client setup and before legacy `repairAlbumYear()`.
3. The pass collects albums missing any target field or missing a primary genre in `album_info_json`.
4. MusicBrainz enrichment runs first.
5. Discogs enrichment runs second only when configured.
6. Provider results are normalized into a shared album metadata payload.
7. A minimal matching guard rejects results whose normalized album title or artist name is clearly unrelated.
8. Only empty album fields are filled.
9. Empty `Track.year` values are backfilled from the album year.
10. Empty `Track.genre` values are backfilled from `primary_genre`.
11. `album_info_json` records providers used, source URLs, and field changes.
12. Review task snapshots include enrichment details.

**Primary Genre Rule**
- Use the first Discogs genre if present.
- Otherwise use the first Discogs style.
- If Discogs is unavailable, do not invent a primary genre from MusicBrainz release type.
- Do not introduce multi-value scoring or conflict resolution in this phase.

**Review Task Behavior**
- Review tasks remain album-scoped and post-write.
- If enrichment changes an album that already has a pending album review task, update that task snapshot.
- If enrichment changes an existing album without a pending album review task, create an album review task with reason `external_enrichment`.
- The task snapshot should include:
  - album fields updated automatically
  - track fields backfilled automatically
  - providers used
  - source URLs
  - enrichment timestamp

This preserves human auditability even though enrichment writes directly to the main library.

**Web UX Exposure**
- Metadata inbox:
  - continue showing cover and year
  - add compact release type and style summary when present
  - show provider summary for external enrichment tasks
- Review task page:
  - show `release_date`
  - show `release_type`
  - show `genres/styles`
  - show which providers updated which fields
- Album detail page:
  - show `release_date`
  - show `release_type`
  - show `genres/styles`

**API Exposure**
- Keep relying on existing standard fields for broad client compatibility:
  - `coverArt`
  - `year`
  - `genre`
- Add non-standard album extension fields to album endpoints through `Album.as_subsonic_album()`:
  - `releaseDate`
  - `releaseType`
  - `styles`
  - `musicBrainzId`
  - `discogsId`

This is intentionally additive. Third-party Subsonic clients may ignore these extensions, but first-party UI and future clients can use them immediately.

**Error Handling**
- A single provider failure must not abort the other provider.
- A single album failure must not abort the full enrichment pass.
- Missing Discogs token must skip Discogs cleanly.
- HTTP `429` or network timeouts must log and skip, not retry aggressively inside scan loops.
- Enrichment should log provider-specific failures with album identity context.
- Provider clients should use module loggers, not `print()`.

**Testing Strategy**
- Schema and migration tests for new album fields and config.
- Provider normalization tests for MusicBrainz and Discogs payloads.
- Pipeline tests for:
  - empty-only writes
  - track year backfill
  - track genre backfill
  - Discogs disabled behavior
  - provider isolation on failures
  - review task creation for `external_enrichment`
- API tests for album extension fields.
- Frontend tests for metadata inbox, review task, and album detail exposure.
- Watcher/scan regression tests to ensure the new pass does not regress post-scan behavior.

**Implementation Notes**
- Keep real network calls behind small provider client functions so tests can use deterministic payloads.
- Avoid adding a new dependency unless the standard `requests` stack is insufficient.
- Do not alter existing Last.fm scrobbling behavior.
- Do not change existing cover repair behavior except to share normalized MusicBrainz helpers if doing so remains low-risk.
