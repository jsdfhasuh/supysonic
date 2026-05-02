# Album UX Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add album-first external enrichment using `MusicBrainz + Discogs`, persist only missing high-impact UX fields into the main library, backfill empty track year/genre fields, and expose the results in both web UI and album API responses.

**Architecture:** Extend scan post-processing with a dedicated album enrichment pass that normalizes `MusicBrainz` and `Discogs` responses into a shared structure. Persist structured album fields into `Album`, extensible provider data into `album_info_json`, and backfill only empty `Track.year` / `Track.genre` values so existing browse behavior improves immediately.

**Tech Stack:** Python, Flask, Peewee, unittest, HTTP API integration.

---

### Task 1: Add Album Enrichment Schema And Config

**Files:**
- Modify: `supysonic/db.py`
- Modify: `supysonic/config.py`
- Modify: `supysonic/schema/sqlite.sql`
- Modify: `supysonic/schema/postgres.sql`
- Modify: `supysonic/schema/mysql.sql`
- Create: `supysonic/schema/migration/sqlite/20260503.py`
- Create: `supysonic/schema/migration/postgres/20260503.sql`
- Create: `supysonic/schema/migration/mysql/20260503.sql`
- Modify: `config.sample`
- Modify: `docs/setup/configuration.rst`
- Test: `tests/base/test_album_enrichment_schema.py`

**Step 1: Write the failing test**

Verify that `Album` exposes the new persistence fields and config includes Discogs.

```python
def test_album_enrichment_columns_exist(self):
    columns = {row[1] for row in db.db.execute_sql("PRAGMA table_info(album)").fetchall()}
    self.assertIn("release_date", columns)
    self.assertIn("release_type", columns)
    self.assertIn("album_info_json", columns)
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_schema`

Expected: FAIL because the new columns and config section do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `Album.release_date` as nullable string field
- `Album.release_type` as nullable string field
- `Album.album_info_json` as nullable text field
- `DISCOGS` config section in `DefaultConfig`
- Discogs config sample and docs entries
- schema version bump plus provider migrations

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_schema`

Expected: PASS.

### Task 2: Add Provider Clients And Normalizers

**Files:**
- Modify: `supysonic/MusicBrainz.py`
- Create: `supysonic/discogs.py`
- Create: `supysonic/scanner_func/scanner_album_enrich.py`
- Test: `tests/base/test_album_enrichment_providers.py`

**Step 1: Write the failing test**

Add provider normalization tests for the shared enrichment structure.

```python
def test_discogs_primary_genre_prefers_first_genre(self):
    payload = {"genres": ["Rock"], "styles": ["Indie Rock"]}
    result = normalizeDiscogsAlbum(payload)
    self.assertEqual(result["primary_genre"], "Rock")
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_providers`

Expected: FAIL because the Discogs client and normalization helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- MusicBrainz helper for:
  - `release_date`
  - `year`
  - `release_type`
  - `musicbrainz_id`
- Discogs client with configuration-backed requests
- shared normalizers in `scanner_album_enrich.py`
- provider result merge helper

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_providers`

Expected: PASS.

### Task 3: Build The Album Enrichment Pipeline

**Files:**
- Modify: `supysonic/scanner_func/scanner_enrich.py`
- Modify: `supysonic/scanner_func/scanner_review_tasks.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_album_enrichment_pipeline.py`

**Step 1: Write the failing test**

Cover empty-only writes and track backfill behavior.

```python
def test_pipeline_backfills_empty_track_genre_only(self):
    track.genre = None
    track.save()
    runAlbumEnrichment(scanner, album)
    self.assertEqual(Track[track.id].genre, "Rock")
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_pipeline`

Expected: FAIL because the enrichment pass is not implemented.

**Step 3: Write minimal implementation**

Implement in `scanner_enrich.py`:
- collect albums missing UX fields
- fetch MusicBrainz first
- fetch Discogs second
- merge normalized results
- fill only empty album fields
- backfill only empty `Track.year`
- backfill only empty `Track.genre`
- record enrichment details for the review snapshot

Add small `Album` helpers in `db.py` if needed for `album_info_json` read/write.

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_pipeline`

Expected: PASS.

### Task 4: Extend Review Task Snapshots

**Files:**
- Modify: `supysonic/scanner_func/scanner_review_tasks.py`
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/base/test_album_enrichment_review_tasks.py`

**Step 1: Write the failing test**

Verify that automatic enrichment details appear in the review task snapshot.

```python
def test_review_snapshot_records_provider_updates(self):
    snapshot = json.loads(task.snapshot_json)
    self.assertEqual(snapshot["enrichment"]["providers_used"], ["musicbrainz", "discogs"])
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_review_tasks`

Expected: FAIL because review snapshots do not yet include enrichment details.

**Step 3: Write minimal implementation**

Extend snapshot generation to include:
- updated album fields
- updated track fields
- provider list
- enrichment timestamp

Update metadata inbox / task view data extraction to read the extended snapshot safely.

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_review_tasks`

Expected: PASS.

### Task 5: Expose New Album Fields In The API

**Files:**
- Modify: `supysonic/db.py`
- Modify: `supysonic/api/browse.py`
- Test: `tests/base/test_album_enrichment_api.py`

**Step 1: Write the failing test**

Verify album endpoints expose the new extension fields.

```python
def test_get_album_info2_returns_release_type_and_styles(self):
    payload = response.json["subsonic-response"]["albumInfo"]
    self.assertEqual(payload["releaseType"], "album")
    self.assertEqual(payload["styles"], ["Indie Rock"])
```

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_api`

Expected: FAIL because the album extension fields are not returned yet.

**Step 3: Write minimal implementation**

Expose in `Album.as_subsonic_album(...)`:
- `releaseDate`
- `releaseType`
- `styles`
- `musicBrainzId`
- `discogsId`

Keep compatibility by leaving existing standard fields intact.

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_api`

Expected: PASS.

### Task 6: Expose New Album Fields In The Web UI

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `supysonic/templates/metadata-review-task.html`
- Modify: `supysonic/templates/partials/metadata-inbox-content.html`
- Modify: `supysonic/templates/partials/metadata-review-album-panel.html`
- Modify: `supysonic/templates/metadata-album.html`
- Modify: `supysonic/templates/partials/metadata-album-content.html`
- Test: `tests/frontend/test_metadata_album_enrichment.py`

**Step 1: Write the failing test**

Verify web surfaces expose the enriched album fields.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_album_enrichment`

Expected: FAIL because the templates do not show the new fields yet.

**Step 3: Write minimal implementation**

Expose in the UI:
- inbox card summary
- review task album panel
- album detail page

Show:
- `release_date`
- `release_type`
- `styles`
- enrichment source summary

**Step 4: Run test to verify it passes**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_album_enrichment`

Expected: PASS.

### Task 7: Focused Regression Coverage

**Files:**
- Modify: none unless failures require it
- Test:
  - `tests.base.test_album_enrichment_schema`
  - `tests.base.test_album_enrichment_providers`
  - `tests.base.test_album_enrichment_pipeline`
  - `tests.base.test_album_enrichment_review_tasks`
  - `tests.base.test_album_enrichment_api`
  - `tests.frontend.test_metadata_album_enrichment`
  - `tests.base.test_watcher`
  - `tests.base.test_watcher_nfo_ignore`
  - `tests.base.test_daemon_logging`

**Step 1: Run the focused enrichment suite**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_album_enrichment_schema tests.base.test_album_enrichment_providers tests.base.test_album_enrichment_pipeline tests.base.test_album_enrichment_review_tasks tests.base.test_album_enrichment_api tests.frontend.test_metadata_album_enrichment`

Expected: PASS.

**Step 2: Run nearby scan/watcher regressions**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_watcher tests.base.test_watcher_nfo_ignore tests.base.test_daemon_logging`

Expected: PASS.

### Task 8: Full Verification

**Files:**
- Modify: none unless failures require it
- Test: full affected suite or full `unittest` run if impact remains uncertain

**Step 1: Run final verification command**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest`

Expected: PASS, or a clearly documented note about any environment-dependent suites that cannot run in the current setup.

### Task 9: Rollout Notes

**Files:**
- Modify: `config.sample`
- Modify: `docs/setup/configuration.rst`

**Step 1: Document Discogs configuration**

Document:
- token
- api URL
- user agent requirements

**Step 2: Document enrichment behavior**

Document that phase 1:
- only fills missing values
- backfills empty `Track.year` and `Track.genre`
- adds non-standard album extension fields to album API responses
- keeps review tasks as post-write verification
