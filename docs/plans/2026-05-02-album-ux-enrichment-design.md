# Album UX Enrichment Design

**Goal:** Improve immediately visible album metadata quality by enriching albums from `MusicBrainz + Discogs`, writing only missing values into the main library, and exposing the results in both the web UI and album API responses.

**Confirmed Constraints**
- Scope is album-first, not artist-first or track-first.
- Prioritize fields with immediate UX impact over archival completeness.
- Write directly to the main library tables rather than a staging area.
- Only fill empty values; never overwrite existing metadata.
- Do not introduce a matching-confidence threshold in this phase.
- Keep review tasks as post-write human verification, not as a gate before persistence.

**Current State**
- Scan post-processing already runs through `Scanner.find_lost_information()` from both full scans and watcher batches.
- Current enrichment covers only:
  - album year
  - album cover
  - artist biography / images
- Existing UI and API already benefit directly from:
  - `coverArt`
  - `year`
  - `genre`
- Existing browsing and similarity behavior often depends on `Track.year` and `Track.genre`, not just album-level fields.

**Chosen Scope For Phase 1**
- Enrich album-facing fields that users can notice immediately:
  - cover art
  - release date
  - year
  - release type
  - genres / styles
- Backfill empty track-level fields needed by current browsing behavior:
  - `Track.year`
  - `Track.genre`

**Why These Fields Matter**
- `coverArt`
  - Visible across album and review surfaces.
  - Highest immediate perceived quality improvement.
- `release_date` and `year`
  - Users can understand chronology better.
  - `year` already appears in review flows and existing browse behavior.
- `release_type`
  - Distinguishes album vs EP vs single vs compilation at a glance.
- `genres / styles`
  - Improves discoverability and descriptive quality.
  - When a primary genre is copied into empty `Track.genre`, current genre browsing and similar-song behavior improve without additional product work.

**Fields Explicitly Deferred**
- `label`
- `country`
- `catalog_number`
- additional external identifiers beyond what is needed for traceability

These are useful for completeness, but do not produce enough immediate UX lift for phase 1.

**Provider Responsibilities**
- `MusicBrainz`
  - primary source for structured release data
  - provides:
    - `release_date`
    - `year`
    - `release_type`
    - `musicbrainz_id`
    - cover fallback when available through current cover-art flow
- `Discogs`
  - primary source for descriptive album taxonomy
  - provides:
    - `genres`
    - `styles`
    - `primary_genre`
    - `discogs_id`
    - cover fallback when useful

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
  "last_enriched_at": "2026-05-02T12:34:56"
}
```

**Why `release_date` Is A String**
- MusicBrainz commonly returns partial dates such as `YYYY` or `YYYY-MM`.
- A strict date field would either reject partial values or require lossy coercion.
- Storing the raw normalized string preserves source fidelity.

**Enrichment Flow**
1. The existing scan/watcher completion flow enters `find_lost_information()`.
2. Existing local repairs continue to run first.
3. A new album UX enrichment pass scans albums missing any of the target fields.
4. MusicBrainz enrichment runs first.
5. Discogs enrichment runs second.
6. Results are merged into a normalized album metadata payload.
7. Only empty album fields are filled.
8. Empty `Track.year` values are backfilled from the album year.
9. Empty `Track.genre` values are backfilled from `primary_genre`.
10. The review task snapshot is updated with provider and field-change details.

**Primary Genre Rule**
- Use the first Discogs genre if present.
- Otherwise use the first Discogs style.
- Do not introduce multi-value scoring or conflict resolution in this phase.

**Web UX Exposure**
- Metadata inbox
  - continue showing cover and year
  - add compact `release_type` and style summary
- Review task page
  - show `release_date`
  - show `release_type`
  - show `genres/styles`
  - show which providers updated which fields
- Album detail page
  - show `release_date`
  - show `release_type`
  - show `genres/styles`

**API Exposure**
- Keep relying on existing standard fields for broad client compatibility:
  - `coverArt`
  - `year`
  - `genre`
- Add non-standard album extension fields to album endpoints:
  - `releaseDate`
  - `releaseType`
  - `styles`
  - `musicBrainzId`
  - `discogsId`

This is intentionally additive. Third-party Subsonic clients may ignore these extensions, but first-party UI and future clients can use them immediately.

**Review Task Behavior**
- Review tasks remain album-scoped and post-write.
- The task snapshot should include:
  - album fields updated automatically
  - track fields backfilled automatically
  - before/after values where practical
  - providers used
  - enrichment timestamp

This preserves human auditability even though enrichment writes directly to the main library.

**Error Handling**
- A single provider failure must not abort the other provider.
- A single album failure must not abort the full enrichment pass.
- Enrichment should log provider-specific failures with album identity context.
- MusicBrainz requests must use a meaningful `User-Agent` and respect the documented rate limit expectations.
- Discogs authentication and request policy must be confirmed at implementation time before finalizing client behavior.

**Testing Strategy**
- Schema and migration tests for new album fields and config.
- Provider normalization tests for MusicBrainz and Discogs payloads.
- Pipeline tests for:
  - empty-only writes
  - track year backfill
  - track genre backfill
  - provider isolation on failures
- API tests for album extension fields.
- Frontend tests for metadata inbox, review task, and album detail exposure.
- Watcher/scan regression tests to ensure the new pass does not regress post-scan behavior.

**Open Implementation Note**
- Discogs credential, token, and rate-limit handling still need confirmation before execution. The architecture above assumes that the client can be configured cleanly through a new `DISCOGS` config section.
