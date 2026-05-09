# Album UX Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add album-first external enrichment using MusicBrainz by default and optional Discogs, persist only missing high-impact UX fields into the main library, backfill empty track year/genre fields, and expose results in review, web, and API surfaces.

**Architecture:** Extend scan post-processing with a dedicated album enrichment pass inserted in `scanner_enrich.findLostInformation()` before legacy year/cover repair. Normalize MusicBrainz and Discogs responses into one payload, persist direct structured fields on `Album`, store extensible provider data in `album_info_json`, and keep Discogs disabled unless configured.

**Tech Stack:** Python, Flask, Peewee, unittest, requests, existing scanner/review task pipeline.

---

## Execution Rules

- Use TDD for every behavior change: write the failing test, run it, implement the minimal code, rerun it.
- Use schema version `20260509`; `20260507` is already used by client release schema changes in the current working tree.
- Do not require Discogs for successful enrichment.
- Do not overwrite non-empty album or track metadata.
- Do not commit unless the user explicitly asks for a commit.
- Test commands use the current known-good interpreter `"/root/enter/envs/supysonic/bin/python"`; replace it with `python` only when running in a different prepared environment.

---

### Task 1: Add Album Enrichment Schema And Config

**Files:**
- Modify: `supysonic/db.py`
- Modify: `supysonic/config.py`
- Modify: `supysonic/schema/sqlite.sql`
- Modify: `supysonic/schema/postgres.sql`
- Modify: `supysonic/schema/mysql.sql`
- Create: `supysonic/schema/migration/sqlite/20260509.sql`
- Create: `supysonic/schema/migration/postgres/20260509.sql`
- Create: `supysonic/schema/migration/mysql/20260509.sql`
- Modify: `config.sample`
- Modify: `docs/setup/configuration.rst` if this repository copy contains that file
- Test: `tests/base/test_album_enrichment_schema.py`

**Step 1: Write the failing schema/config test**

Create `tests/base/test_album_enrichment_schema.py` with tests that verify the SQLite schema exposes the new fields and the default config contains MusicBrainz and Discogs sections.

```python
import unittest
from pathlib import Path

from supysonic import db

from ..testbase import TestBase, TestConfig


class AlbumEnrichmentSchemaTestCase(TestBase):
    def test_album_enrichment_columns_exist(self):
        columns = {
            row[1]
            for row in db.db.execute_sql("PRAGMA table_info(album)").fetchall()
        }

        self.assertIn("release_date", columns)
        self.assertIn("release_type", columns)
        self.assertIn("album_info_json", columns)

    def test_album_enrichment_config_defaults_exist(self):
        config = TestConfig(with_webui=False, with_api=False)

        self.assertIn("api_url", config.MUSICBRAINZ)
        self.assertIn("user_agent", config.MUSICBRAINZ)
        self.assertFalse(config.DISCOGS["enabled"])
        self.assertEqual(config.DISCOGS["token"], "")

    def test_packaged_sqlite_schema_contains_album_enrichment_columns(self):
        schema_path = Path(__file__).resolve().parents[2] / "supysonic" / "schema" / "sqlite.sql"

        schema = schema_path.read_text(encoding="utf-8")

        self.assertIn("release_date", schema)
        self.assertIn("release_type", schema)
        self.assertIn("album_info_json", schema)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_schema`

Expected: FAIL because the new columns and config sections do not exist yet.

**Step 3: Implement minimal schema/config**

Implement:
- `SCHEMA_VERSION = "20260509"` in `supysonic/db.py`.
- `Album.release_date = CharField(max_length=32, null=True)`.
- `Album.release_type = CharField(max_length=64, null=True)`.
- `Album.album_info_json = TextField(null=True)`.
- `DefaultConfig.MUSICBRAINZ` with:
  - `api_url = "https://musicbrainz.org/ws/2"`
  - `cover_art_api_url = "https://coverartarchive.org"`
  - `user_agent = "Supysonic/1.0"`
  - `request_delay_seconds = 1.0`
- `DefaultConfig.DISCOGS` with:
  - `enabled = False`
  - `api_url = "https://api.discogs.com"`
  - `token = ""`
  - `user_agent = "Supysonic/1.0"`
  - `request_delay_seconds = 1.0`
- Initial schema changes for SQLite, PostgreSQL, and MySQL.
- `20260509.sql` migrations using simple `ALTER TABLE ... ADD COLUMN ...` statements.
- `config.sample` documentation for `[musicbrainz]` and `[discogs]`.

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_schema`

Expected: PASS.

**Step 5: Check migration safety**

Run: `git diff --check`

Expected: no output.

---

### Task 2: Add Provider Normalizers And Optional Discogs Client

**Files:**
- Modify: `supysonic/MusicBrainz.py`
- Create: `supysonic/discogs.py`
- Create: `supysonic/scanner_func/scanner_album_enrich.py`
- Test: `tests/base/test_album_enrichment_providers.py`

**Step 1: Write failing provider normalization tests**

Create `tests/base/test_album_enrichment_providers.py` with deterministic payload tests. Do not hit real networks.

```python
import unittest

import requests

from supysonic.scanner_func.scanner_album_enrich import (
    isAlbumMatchCandidate,
    mergeAlbumEnrichment,
    normalizeDiscogsAlbum,
    normalizeMusicBrainzAlbum,
)
from supysonic.discogs import DiscogsClient


class AlbumEnrichmentProviderTestCase(unittest.TestCase):
    def test_musicbrainz_normalizer_extracts_release_date_year_and_type(self):
        payload = {
            "id": "mb-release-id",
            "date": "2024-03-15",
            "release-group": {"primary-type": "Album"},
        }

        result = normalizeMusicBrainzAlbum(payload)

        self.assertEqual(result["musicbrainz_id"], "mb-release-id")
        self.assertEqual(result["release_date"], "2024-03-15")
        self.assertEqual(result["year"], "2024")
        self.assertEqual(result["release_type"], "album")

    def test_discogs_primary_genre_prefers_first_genre(self):
        payload = {"id": 123, "genres": ["Rock"], "styles": ["Indie Rock"]}

        result = normalizeDiscogsAlbum(payload)

        self.assertEqual(result["discogs_id"], "123")
        self.assertEqual(result["genres"], ["Rock"])
        self.assertEqual(result["styles"], ["Indie Rock"])
        self.assertEqual(result["primary_genre"], "Rock")

    def test_merge_keeps_musicbrainz_structured_fields_and_discogs_taxonomy(self):
        result = mergeAlbumEnrichment(
            {"release_date": "2024", "year": "2024", "release_type": "album"},
            {"genres": ["Rock"], "styles": ["Indie Rock"], "primary_genre": "Rock"},
        )

        self.assertEqual(result["release_date"], "2024")
        self.assertEqual(result["primary_genre"], "Rock")

    def test_matching_guard_rejects_obviously_unrelated_album(self):
        self.assertFalse(
            isAlbumMatchCandidate(
                artist_name="Radiohead",
                album_name="OK Computer",
                candidate_artist="Miles Davis",
                candidate_album="Kind of Blue",
            )
        )

    def test_discogs_client_is_disabled_without_token_even_when_enabled(self):
        client = DiscogsClient({
            "enabled": True,
            "token": "",
            "api_url": "https://api.discogs.com",
            "user_agent": "Supysonic/1.0",
        })

        self.assertFalse(client.is_enabled())
        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_is_disabled_with_missing_config(self):
        client = DiscogsClient({})

        self.assertFalse(client.is_enabled())
        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_returns_empty_on_rate_limit(self):
        class ResponseStub:
            status_code = 429

            def json(self):
                return {}

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=lambda *args, **kwargs: ResponseStub(),
        )

        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_returns_empty_on_http_error(self):
        class ResponseStub:
            status_code = 500

            def json(self):
                return {"message": "server error"}

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=lambda *args, **kwargs: ResponseStub(),
        )

        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_returns_empty_on_network_error(self):
        def raise_timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("timeout")

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=raise_timeout,
        )

        self.assertEqual(client.search_album("Artist", "Album"), {})


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_providers`

Expected: FAIL because `scanner_album_enrich.py` and normalizers do not exist.

**Step 3: Implement minimal normalizers and clients**

Implement in `supysonic/scanner_func/scanner_album_enrich.py`:
- `normalizeMusicBrainzAlbum(payload)`.
- `normalizeDiscogsAlbum(payload)`.
- `mergeAlbumEnrichment(musicbrainz_result, discogs_result)`.
- `isAlbumMatchCandidate(artist_name, album_name, candidate_artist, candidate_album)`.
- small helpers for list normalization and release type normalization.
- a conservative matching guard that rejects only obviously unrelated title/artist pairs; ambiguous values should skip writing rather than force a match.

Implement in `supysonic/MusicBrainz.py`:
- keep existing public functions working.
- route new album lookup helpers through configured URL/User-Agent when called by the enrichment pass.
- replace new code `print()` usage with `logger.warning(...)`.

Implement in `supysonic/discogs.py`:
- `DiscogsClient(config, request_get=None)` where `request_get` defaults to `requests.get`.
- `is_enabled()` returns true only when `enabled` is true and `token` is non-empty.
- `search_album(artist_name, album_name)` returns `{}` on missing config, HTTP errors, or rate limits.
- `search_album(...)` returns `{}` for HTTP `429` and logs without retrying aggressively.
- `search_album(...)` catches `requests.exceptions.RequestException` and returns `{}`.
- Use token auth header or query parameter consistently; do not log the token.

**Step 4: Run provider tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_providers`

Expected: PASS.

---

### Task 3: Build The Album Enrichment Pipeline

**Files:**
- Modify: `supysonic/scanner_func/scanner_album_enrich.py`
- Modify: `supysonic/scanner_func/scanner_enrich.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_album_enrichment_pipeline.py`

**Step 1: Write failing pipeline tests**

Create `tests/base/test_album_enrichment_pipeline.py` covering empty-only writes, track backfill behavior, candidate selection, and failure isolation.

Add a small fixture helper in this test module to create at least two albums with tracks, so failure-isolation tests do not depend on implicit database contents.

```python
import json
import unittest

from supysonic.db import Album, Track
from supysonic.scanner_func.scanner_album_enrich import (
    applyAlbumEnrichment,
    collectAlbumsNeedingEnrichment,
    runAlbumEnrichmentPass,
)

from ..testbase import TestBase


class AlbumEnrichmentPipelineTestCase(TestBase):
    def test_apply_enrichment_fills_empty_album_fields_only(self):
        album = Album.select().first()
        album.year = "1999"
        album.save()

        changes = applyAlbumEnrichment(
            album,
            {
                "year": "2024",
                "release_date": "2024-03-15",
                "release_type": "album",
                "primary_genre": "Rock",
                "providers_used": ["musicbrainz", "discogs"],
            },
        )

        updated = Album[album.id]
        self.assertEqual(updated.year, "1999")
        self.assertEqual(updated.release_date, "2024-03-15")
        self.assertEqual(updated.release_type, "album")
        self.assertIn("release_date", changes["album"])

    def test_apply_enrichment_backfills_empty_track_genre_only(self):
        album = Album.select().first()
        empty_track = album.tracks.first()
        empty_track.genre = None
        empty_track.save()

        changes = applyAlbumEnrichment(album, {"primary_genre": "Rock"})

        self.assertEqual(Track[empty_track.id].genre, "Rock")
        self.assertIn(str(empty_track.id), changes["tracks"]["genre"])

    def test_apply_enrichment_records_album_info_json(self):
        album = Album.select().first()

        applyAlbumEnrichment(
            album,
            {"musicbrainz_id": "mbid", "providers_used": ["musicbrainz"]},
        )

        info = json.loads(Album[album.id].album_info_json)
        self.assertEqual(info["musicbrainz_id"], "mbid")
        self.assertEqual(info["providers_used"], ["musicbrainz"])

    def test_collect_albums_needing_enrichment_skips_complete_album(self):
        album = Album.select().first()
        album.year = "2024"
        album.release_date = "2024-03-15"
        album.release_type = "album"
        album.album_info_json = json.dumps({"primary_genre": "Rock"})
        album.save()

        candidates = list(collectAlbumsNeedingEnrichment())

        self.assertNotIn(album.id, {candidate.id for candidate in candidates})

    def test_album_enrichment_pass_continues_after_provider_failure(self):
        album = Album.select().first()

        class FailingMusicBrainzClient:
            def search_album(self, artist_name, album_name):
                raise RuntimeError("provider down")

        class DiscogsClientStub:
            def is_enabled(self):
                return True

            def search_album(self, artist_name, album_name):
                return {"genres": ["Rock"]}

        scanner = type("ScannerStub", (), {})()

        runAlbumEnrichmentPass(
            scanner,
            musicbrainz_client=FailingMusicBrainzClient(),
            discogs_client=DiscogsClientStub(),
        )

        info = json.loads(Album[album.id].album_info_json)
        self.assertEqual(info["primary_genre"], "Rock")
        self.assertIn(album.id, scanner.review_task_enriched_album_ids)

    def test_album_enrichment_pass_continues_after_single_album_failure(self):
        albums = createTwoAlbumEnrichmentFixtures()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                if album_name == albums[0].name:
                    raise RuntimeError("first album failed")
                return {"date": "2024", "release-group": {"primary-type": "Album"}}

        scanner = type("ScannerStub", (), {})()

        runAlbumEnrichmentPass(
            scanner,
            albums=albums,
            musicbrainz_client=MusicBrainzClientStub(),
            discogs_client=None,
        )

        self.assertIsNone(Album[albums[0].id].release_date)
        self.assertEqual(Album[albums[1].id].release_date, "2024")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_pipeline`

Expected: FAIL because `applyAlbumEnrichment` does not exist.

**Step 3: Implement minimal pipeline helpers**

Implement in `scanner_album_enrich.py`:
- `getAlbumInfo(album)` to safely decode `album.album_info_json`.
- `setAlbumInfo(album, info)` to write stable JSON.
- `collectAlbumsNeedingEnrichment()`.
- `applyAlbumEnrichment(album, enrichment)`.
- `runAlbumEnrichmentPass(scanner, albums=None, musicbrainz_client=None, discogs_client=None, logger=None)` so tests can pass deterministic album sets.

Implementation rules:
- Fill `Album.year` only if empty.
- Fill `Album.release_date` only if empty.
- Fill `Album.release_type` only if empty.
- Backfill `Track.year` only when empty.
- Backfill `Track.genre` only when empty and `primary_genre` exists.
- Always merge provider metadata into `album_info_json` without deleting unrelated existing keys.
- `collectAlbumsNeedingEnrichment()` should include albums missing any of `year`, `release_date`, `release_type`, or `album_info_json.primary_genre`.
- `collectAlbumsNeedingEnrichment()` should skip albums that already have all target fields.
- Provider exceptions should be caught per provider and per album so one provider or one album cannot abort the whole pass.

Modify `scanner_enrich.findLostInformation()`:
- Run `runAlbumEnrichmentPass(scanner, logger=logger)` after `buildExternalMetadataClients(scanner)` and before `repairAlbumYear()`.
- Keep existing `repairAlbumYear()`, `repairAlbumCover()`, artist profile, and image repair behavior unchanged.

**Step 4: Run pipeline tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_pipeline`

Expected: PASS.

**Step 5: Run nearby scanner regression**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`

Expected: PASS, or document existing unrelated failures with exact output.

---

### Task 4: Extend Review Task Audit Trail

**Files:**
- Modify: `supysonic/scanner_func/scanner_review_tasks.py`
- Modify: `supysonic/scanner_func/scanner_album_enrich.py`
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/base/test_album_enrichment_review_tasks.py`

**Step 1: Write failing review task tests**

Create `tests/base/test_album_enrichment_review_tasks.py`.

```python
import json
import unittest

from supysonic.db import Album, ReviewTask
from supysonic.scanner_func.scanner_review_tasks import (
    EXTERNAL_ENRICHMENT_REVIEW_REASON,
    METADATA_REVIEW_TASK_TYPE,
    buildAlbumReviewSnapshot,
    createReviewTasks,
)

from ..testbase import TestBase


class AlbumEnrichmentReviewTaskTestCase(TestBase):
    def test_album_review_snapshot_includes_enrichment_summary(self):
        album = Album.select().first()
        album.album_info_json = json.dumps({"providers_used": ["musicbrainz"]})
        album.save()

        snapshot = json.loads(buildAlbumReviewSnapshot(album))

        self.assertEqual(snapshot["enrichment"]["providers_used"], ["musicbrainz"])

    def test_external_enrichment_creates_album_review_task(self):
        album = Album.select().first()
        scanner = type("ScannerStub", (), {"review_task_enriched_album_ids": {album.id}})()

        createReviewTasks(scanner)

        task = ReviewTask.get(ReviewTask.entity_id == str(album.id))
        self.assertEqual(task.reason, EXTERNAL_ENRICHMENT_REVIEW_REASON)

    def test_external_enrichment_updates_existing_pending_album_task(self):
        album = Album.select().first()
        ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type=METADATA_REVIEW_TASK_TYPE,
            status="pending",
            reason="new_album",
            pending_key=f"album:{album.id}:pending",
            snapshot_json="{}",
        )
        scanner = type("ScannerStub", (), {"review_task_enriched_album_ids": {album.id}})()

        createReviewTasks(scanner)

        self.assertEqual(ReviewTask.select().where(ReviewTask.entity_id == str(album.id)).count(), 1)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_review_tasks`

Expected: FAIL because `EXTERNAL_ENRICHMENT_REVIEW_REASON` and snapshot enrichment data do not exist.

**Step 3: Implement review task audit trail**

Implement:
- `EXTERNAL_ENRICHMENT_REVIEW_REASON = "external_enrichment"`.
- `rememberExternalEnrichedAlbum(scanner, album)` helper.
- `buildAlbumReviewSnapshot(album)` enrichment section from `album_info_json`.
- `createAlbumReviewTasks(scanner)` support for `scanner.review_task_enriched_album_ids`.
- Before creating an `external_enrichment` task, search for any existing pending album review task for the same album and update its snapshot.
- Only when no pending album review task exists, create a new task with pending key `album:{album.id}:pending:external_enrichment`.

Update `runAlbumEnrichmentPass()`:
- Call `rememberExternalEnrichedAlbum(scanner, album)` when `applyAlbumEnrichment()` changes any album or track field.

**Step 4: Run review task tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_review_tasks`

Expected: PASS.

---

### Task 5: Expose Album Enrichment Fields In API Responses

**Files:**
- Modify: `supysonic/db.py`
- Test: `tests/base/test_album_enrichment_api.py` or existing API test module if it already has album response helpers

**Step 1: Write failing API output test**

Prefer testing `Album.as_subsonic_album()` directly to keep this task narrow.

```python
import json
import unittest

from supysonic.db import Album, User

from ..testbase import TestBase


class AlbumEnrichmentApiTestCase(TestBase):
    def test_as_subsonic_album_returns_enrichment_extensions(self):
        album = Album.select().first()
        album.release_date = "2024-03-15"
        album.release_type = "album"
        album.album_info_json = json.dumps({
            "styles": ["Indie Rock"],
            "musicbrainz_id": "mbid",
            "discogs_id": "123",
        })
        album.save()
        user = User.get(User.name == "alice")

        payload = Album[album.id].as_subsonic_album(user, "test-client")

        self.assertEqual(payload["releaseDate"], "2024-03-15")
        self.assertEqual(payload["releaseType"], "album")
        self.assertEqual(payload["styles"], ["Indie Rock"])
        self.assertEqual(payload["musicBrainzId"], "mbid")
        self.assertEqual(payload["discogsId"], "123")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_api`

Expected: FAIL because the extension fields are not returned.

**Step 3: Implement API extension fields**

Modify `Album.as_subsonic_album(...)`:
- Decode `album_info_json` safely.
- Add `releaseDate` when `Album.release_date` exists.
- Add `releaseType` when `Album.release_type` exists.
- Add `styles` when JSON `styles` exists.
- Add `musicBrainzId` when JSON `musicbrainz_id` exists.
- Add `discogsId` when JSON `discogs_id` exists.
- Do not change existing `year`, `genre`, `coverArt`, or `participants` behavior.

**Step 4: Run API tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_api`

Expected: PASS.

---

### Task 6: Expose Album Enrichment In Review And Album Web UI

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `supysonic/templates/metadata-review-task.html`
- Modify: `supysonic/templates/partials/metadata-inbox-content.html`
- Modify: `supysonic/templates/partials/metadata-review-album-panel.html`
- Modify: `supysonic/templates/partials/metadata-album-content.html`
- Test: `tests/frontend/test_metadata_album_enrichment.py`

**Step 1: Write failing frontend tests**

Create `tests/frontend/test_metadata_album_enrichment.py` covering:
- review task page renders release date, release type, styles, and provider summary.
- metadata inbox shows compact external enrichment summary for `external_enrichment` tasks.
- album list/detail UI has the enriched fields in the JS album payload or rendered HTML.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_album_enrichment`

Expected: FAIL because templates do not show the new fields.

**Step 3: Implement minimal UI exposure**

Implement:
- helper in `metadata.py` to safely decode album enrichment info.
- review task album panel fields:
  - `release_date`
  - `release_type`
  - `styles`
  - providers used
- inbox compact summary:
  - `External enrichment: MusicBrainz, Discogs`
  - release type / primary genre if present
- album content page display-only fields first. Do not make these editable until a separate edit/save path is designed.

**Step 4: Run frontend test**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_album_enrichment`

Expected: PASS.

---

### Task 7: Rollout Documentation

**Files:**
- Modify: `config.sample`
- Modify: `docs/setup/configuration.rst` if present
- Modify: `docs/plans/2026-05-02-album-ux-enrichment-design.md` only if implementation discovers a design mismatch

**Step 1: Document provider behavior**

Document:
- MusicBrainz is the default structured source.
- Discogs is optional and disabled unless configured.
- Discogs token must not be committed.
- Discogs requests are rate-limited and skipped on failure.
- Enrichment only fills empty values.
- Enrichment may create `external_enrichment` review tasks after writing automatic changes.

**Step 2: Verify docs references**

Run: `git diff --check`

Expected: no output.

---

### Task 8: Focused Regression Coverage

**Files:**
- Modify only if failures expose bugs

**Step 1: Run focused album enrichment suite**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest \
  tests.base.test_album_enrichment_schema \
  tests.base.test_album_enrichment_providers \
  tests.base.test_album_enrichment_pipeline \
  tests.base.test_album_enrichment_review_tasks \
  tests.base.test_album_enrichment_api \
  tests.frontend.test_metadata_album_enrichment
```

Expected: PASS.

**Step 2: Run nearby scanner/review regressions**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest \
  tests.base.test_scanner_helpers \
  tests.base.test_watcher \
  tests.base.test_watcher_nfo_ignore \
  tests.base.test_metadata_review_task_model \
  tests.frontend.test_metadata_inbox \
  tests.frontend.test_metadata_review \
  tests.frontend.test_metadata_review_workspace
```

Expected: PASS, or document exact unrelated failures.

**Step 3: Run schema-related regressions**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest \
  tests.base.test_client_release_schema \
  tests.base.test_album_enrichment_schema
```

Expected: PASS.

**Step 4: Run final diff check**

Run: `git diff --check`

Expected: no output.

---

### Task 9: Full Verification Decision

**Files:**
- Modify none unless failures require it

**Step 1: Decide whether full `unittest` is required**

Run full test suite if the scanner, schema, API, or review task impact remains uncertain:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest
```

Expected: PASS, or document known environment-dependent failures with exact module names and error messages.

**Step 2: Prepare handoff summary**

Summarize:
- schema version used
- provider behavior
- Discogs disabled-by-default behavior
- fields written and fields never overwritten
- tests run
- tests not run and why
