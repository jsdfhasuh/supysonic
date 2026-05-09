# DB Layer Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split `supysonic/db.py` into a small compatibility facade plus focused modules under `supysonic/db_layer/` without changing database schema or public import behavior.

**Architecture:** Keep `supysonic.db` as the stable public API during the refactor. Move responsibilities into `supysonic/db_layer/` in low-risk phases: core database primitives first, schema/runtime next, Subsonic serializers next, and only then domain models grouped by dependency clusters.

**Tech Stack:** Python, Peewee ORM, unittest, existing SQL schema/migration files, setuptools package data.

---

## Guardrails

- Do not create a `supysonic/db/` package because it conflicts with the existing `supysonic/db.py` module.
- Use `supysonic/db_layer/` for extracted modules.
- Preserve `from supysonic.db import Album, Track, init_database` and `from supysonic import db` behavior throughout the refactor.
- Do not change table names, field names, schema SQL, migration versions, or API response payloads.
- Do not combine feature work with this refactor.
- Keep every task small enough to review independently.
- Run the narrow tests listed in each task before moving to the next task.
- If a task introduces circular imports, prefer local imports inside methods before adding new abstractions.

## Target Module Layout

```text
supysonic/db_layer/
  __init__.py
  core.py
  schema.py
  runtime.py
  serializers.py
  library.py
  users.py
  annotations.py
  playlists.py
  review_tasks.py
  emo.py
  client_releases.py
  misc.py
```

## Public Compatibility Contract

`supysonic/db.py` remains the public facade until a future breaking-change release. It must continue exporting these names:

```python
SCHEMA_VERSION
db
now
random
PrimaryKeyField
Meta
PathMixin
Image
Folder
Artist
Album
ReviewTask
AlbumReviewTask
AlbumArtist
Track
TrackArtist
User
User_Play_Activity
ClientPrefs
EmoSessionQueue
EmoLocalQueue
EmoPlaybackState
StarredFolder
StarredArtist
StarredAlbum
StarredTrack
RatingFolder
RatingTrack
ChatMessage
Playlist
SharedTrackLink
RadioStation
ClientRelease
execute_sql_resource_script
init_database
release_database
open_connection
close_connection
```

---

### Task 1: Add DB Facade Contract Tests

**Files:**
- Create: `tests/base/test_db_layer_contract.py`
- Do not modify production code in this task.

**Step 1: Write the failing test**

Add a test that documents the public `supysonic.db` API and the planned `db_layer` package path.

```python
import importlib
import unittest


class DbLayerContractTestCase(unittest.TestCase):
    def test_db_facade_exports_existing_public_names(self):
        db_module = importlib.import_module("supysonic.db")
        expected_names = [
            "SCHEMA_VERSION",
            "db",
            "now",
            "random",
            "PrimaryKeyField",
            "Meta",
            "PathMixin",
            "Image",
            "Folder",
            "Artist",
            "Album",
            "ReviewTask",
            "AlbumReviewTask",
            "AlbumArtist",
            "Track",
            "TrackArtist",
            "User",
            "User_Play_Activity",
            "ClientPrefs",
            "EmoSessionQueue",
            "EmoLocalQueue",
            "EmoPlaybackState",
            "StarredFolder",
            "StarredArtist",
            "StarredAlbum",
            "StarredTrack",
            "RatingFolder",
            "RatingTrack",
            "ChatMessage",
            "Playlist",
            "SharedTrackLink",
            "RadioStation",
            "ClientRelease",
            "execute_sql_resource_script",
            "init_database",
            "release_database",
            "open_connection",
            "close_connection",
        ]

        for name in expected_names:
            with self.subTest(name=name):
                self.assertTrue(hasattr(db_module, name))

    def test_db_layer_package_exists(self):
        package = importlib.import_module("supysonic.db_layer")

        self.assertIsNotNone(package)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with `ModuleNotFoundError: No module named 'supysonic.db_layer'`.

**Step 3: Add the empty package**

Create `supysonic/db_layer/__init__.py`:

```python
"""Internal database layer modules.

Public callers should continue importing from supysonic.db until the
compatibility facade is intentionally retired.
"""
```

**Step 4: Run test to verify it passes**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/base/test_db_layer_contract.py supysonic/db_layer/__init__.py
git commit -m "test: add db layer facade contract"
```

---

### Task 2: Extract Core Database Primitives

**Files:**
- Create: `supysonic/db_layer/core.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_db_layer_contract.py`
- Test: `tests/base/test_db.py`

**Step 1: Extend the contract test**

Add assertions that `supysonic.db` and `supysonic.db_layer.core` expose the same core objects.

```python
    def test_core_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        core = importlib.import_module("supysonic.db_layer.core")

        self.assertIs(db_module.db, core.db)
        self.assertIs(db_module.Meta, core.Meta)
        self.assertIs(db_module.PathMixin, core.PathMixin)
        self.assertIs(db_module.now, core.now)
        self.assertIs(db_module.random, core.random)
        self.assertIs(db_module.PrimaryKeyField, core.PrimaryKeyField)
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with `ModuleNotFoundError: No module named 'supysonic.db_layer.core'`.

**Step 3: Move core primitives into `core.py`**

Create `supysonic/db_layer/core.py` with these definitions moved from `supysonic/db.py`:

```python
from datetime import datetime
from hashlib import sha1
from uuid import uuid4

from peewee import DatabaseProxy, Model, MySQLDatabase, UUIDField, fn


def now():
    return datetime.now().replace(microsecond=0)


def random():
    if isinstance(db.obj, MySQLDatabase):
        return fn.rand()
    return fn.random()


def PrimaryKeyField(**kwargs):
    return UUIDField(primary_key=True, default=uuid4, **kwargs)


db = DatabaseProxy()


class _Model(Model):
    class Meta:
        database = db
        legacy_table_names = False


class Meta(_Model):
    key = CharField(32, primary_key=True)
    value = CharField(256)


class PathMixin:
    @classmethod
    def get(cls, *args, **kwargs):
        if kwargs:
            path = kwargs.pop("path", None)
            if path:
                kwargs["_path_hash"] = sha1(path.encode("utf-8")).digest()
        return _Model.get.__func__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        if "path" in kwargs:
            path = kwargs["path"]
            kwargs["_path_hash"] = sha1(path.encode("utf-8")).digest()
        _Model.__init__(self, *args, **kwargs)

    def __setattr__(self, attr, value):
        _Model.__setattr__(self, attr, value)
        if attr == "path":
            _Model.__setattr__(self, "_path_hash", sha1(value.encode("utf-8")).digest())
```

Also import `CharField` in `core.py`. The snippet intentionally mirrors existing behavior; do not rewrite logic.

**Step 4: Update `db.py` imports**

Remove duplicated definitions from `supysonic/db.py` and import them from `core.py`:

```python
from .db_layer.core import _Model, Meta, PathMixin, PrimaryKeyField, db, now, random
```

Remove now-unused imports from `db.py`: `datetime`, `sha1`, `DatabaseProxy`, `Model`, `uuid4`, and `UUIDField` if no longer needed.

**Step 5: Run tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.base.test_db
```

Expected: PASS.

**Step 6: Commit**

```bash
git add supysonic/db_layer/core.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: extract db core primitives"
```

---

### Task 3: Extract Schema Resource Helpers

**Files:**
- Create: `supysonic/db_layer/schema.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_db_layer_contract.py`
- Test: `tests/base/test_album_enrichment_schema.py`
- Test: `tests/base/test_client_release_schema.py`

**Step 1: Add contract coverage**

```python
    def test_schema_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        schema = importlib.import_module("supysonic.db_layer.schema")

        self.assertEqual(db_module.SCHEMA_VERSION, schema.SCHEMA_VERSION)
        self.assertIs(db_module.execute_sql_resource_script, schema.execute_sql_resource_script)
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with `ModuleNotFoundError: No module named 'supysonic.db_layer.schema'`.

**Step 3: Move schema helpers into `schema.py`**

Move from `supysonic/db.py`:

```python
SCHEMA_VERSION = "20260510"
get_resource_text()
list_migrations()
execute_sql_resource_script()
```

`schema.py` imports the shared proxy:

```python
import sys

from .core import db

SCHEMA_VERSION = "20260510"

# Preserve the existing Python < 3.9 resource fallback exactly.
```

Do not move SQL files or migration files.

**Step 4: Update `db.py` imports**

```python
from .db_layer.schema import (
    SCHEMA_VERSION,
    execute_sql_resource_script,
    get_resource_text,
    list_migrations,
)
```

Remove now-unused `sys` and `importlib.resources` fallback blocks from `db.py`.

**Step 5: Run schema tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.base.test_db tests.base.test_album_enrichment_schema tests.base.test_client_release_schema
```

Expected: PASS.

**Step 6: Commit**

```bash
git add supysonic/db_layer/schema.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: extract db schema helpers"
```

---

### Task 4: Extract Runtime Connection and Migration Runner

**Files:**
- Create: `supysonic/db_layer/runtime.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_db_layer_contract.py`
- Test: `tests/base/test_web_startup.py`
- Test: `tests/base/test_cli.py`

**Step 1: Add contract coverage**

```python
    def test_runtime_exports_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        runtime = importlib.import_module("supysonic.db_layer.runtime")

        self.assertIs(db_module.init_database, runtime.init_database)
        self.assertIs(db_module.release_database, runtime.release_database)
        self.assertIs(db_module.open_connection, runtime.open_connection)
        self.assertIs(db_module.close_connection, runtime.close_connection)
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with `ModuleNotFoundError: No module named 'supysonic.db_layer.runtime'`.

**Step 3: Move runtime functions into `runtime.py`**

Move from `supysonic/db.py`:

```python
init_database()
release_database()
open_connection()
close_connection()
```

`runtime.py` needs imports:

```python
import importlib
import os.path
from urllib.parse import urlparse

from playhouse.db_url import parseresult_to_dict, schemes

from .core import Meta, db
from .schema import SCHEMA_VERSION, execute_sql_resource_script, list_migrations
```

Preserve the existing `sqlite:` empty dirname handling.

**Step 4: Update `db.py` imports**

```python
from .db_layer.runtime import close_connection, init_database, open_connection, release_database
```

Remove now-unused `importlib`, `urlparse`, `parseresult_to_dict`, and `schemes` imports from `db.py` if only runtime used them.

**Step 5: Run runtime tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.base.test_db tests.base.test_web_startup tests.base.test_cli
```

Expected: PASS.

**Step 6: Commit**

```bash
git add supysonic/db_layer/runtime.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: extract db runtime helpers"
```

---

### Task 5: Extract Subsonic Serializers Behind Existing Model Methods

**Files:**
- Create: `supysonic/db_layer/serializers.py`
- Modify: `supysonic/db.py`
- Test: `tests/api/test_browse.py`
- Test: `tests/api/test_media.py`
- Test: `tests/api/test_playlist.py`
- Test: `tests/api/test_annotation.py`
- Test: `tests/frontend/test_playlist.py`

**Step 1: Add serializer parity tests**

Create focused tests in `tests/base/test_db_layer_contract.py` that compare the model method object path only after extraction is complete. Do not assert full API payloads here because API tests already cover payload behavior.

```python
    def test_serializer_module_exists(self):
        serializers = importlib.import_module("supysonic.db_layer.serializers")

        for name in (
            "serialize_folder_child",
            "serialize_folder_artist",
            "serialize_folder_directory",
            "serialize_artist",
            "serialize_album",
            "serialize_track_child",
            "serialize_user",
            "serialize_playlist",
            "serialize_radio_station",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(serializers, name))
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with missing `serializers` module or missing functions.

**Step 3: Create `serializers.py`**

Move logic, not signatures, into functions:

```python
def serialize_folder_child(folder, user):
    ...

def serialize_folder_artist(folder, user):
    ...

def serialize_folder_directory(folder, user, client):
    ...

def serialize_artist(artist, user):
    ...

def serialize_album(album, user, server_type=None):
    ...

def serialize_track_child(track, user, prefs):
    ...

def serialize_user(user):
    ...

def serialize_chat_message(message):
    ...

def serialize_playlist(playlist, user, tracks=None):
    ...

def serialize_radio_station(station):
    ...
```

Use local imports at the top of each function or a private helper to avoid circular imports:

```python
def serialize_album(album, user, server_type=None):
    from supysonic.db import Folder, StarredAlbum, Track
    ...
```

Do not alter field names, field order, default values, or exception handling.

**Step 4: Replace model methods with delegation**

In `supysonic/db.py`, keep each existing method but delegate:

```python
def as_subsonic_album(self, user, server_type=None):
    from .db_layer.serializers import serialize_album

    return serialize_album(self, user, server_type)
```

Do this for:

```text
Folder.as_subsonic_child
Folder.as_subsonic_artist
Folder.as_subsonic_directory
Artist.as_subsonic_artist
Album.as_subsonic_album
Track.as_subsonic_child
User.as_subsonic_user
ChatMessage.responsize
Playlist.as_subsonic_playlist
RadioStation.as_subsonic_station
```

Keep non-serialization methods in place for now: `prune()`, `delete_hierarchy()`, `get_tracks()`, `add()`, `remove_at_indexes()`.

**Step 5: Run API serialization tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.api.test_browse tests.api.test_media tests.api.test_playlist tests.api.test_annotation tests.frontend.test_playlist
```

Expected: PASS.

**Step 6: Commit**

```bash
git add supysonic/db_layer/serializers.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: extract subsonic serializers"
```

---

### Task 6: Extract Low-Dependency Models First

**Files:**
- Create: `supysonic/db_layer/emo.py`
- Create: `supysonic/db_layer/client_releases.py`
- Modify: `supysonic/db.py`
- Test: `tests/base/test_emo_ws_store.py`
- Test: `tests/base/test_client_release_schema.py`
- Test: `tests/frontend/test_client_releases.py`

**Step 1: Add contract coverage**

```python
    def test_low_dependency_models_are_shared_with_facade(self):
        db_module = importlib.import_module("supysonic.db")
        emo = importlib.import_module("supysonic.db_layer.emo")
        client_releases = importlib.import_module("supysonic.db_layer.client_releases")

        self.assertIs(db_module.EmoSessionQueue, emo.EmoSessionQueue)
        self.assertIs(db_module.EmoLocalQueue, emo.EmoLocalQueue)
        self.assertIs(db_module.EmoPlaybackState, emo.EmoPlaybackState)
        self.assertIs(db_module.ClientRelease, client_releases.ClientRelease)
```

**Step 2: Run test to verify it fails**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract
```

Expected: FAIL with missing modules.

**Step 3: Move models**

Move these classes from `supysonic/db.py` to `supysonic/db_layer/emo.py`:

```python
EmoSessionQueue
EmoLocalQueue
EmoPlaybackState
```

Move `ClientRelease` to `supysonic/db_layer/client_releases.py`.

Both modules import from `core.py`:

```python
from peewee import BooleanField, CharField, DateTimeField, IntegerField, TextField

from .core import PrimaryKeyField, _Model, now
```

**Step 4: Re-export from `db.py`**

```python
from .db_layer.client_releases import ClientRelease
from .db_layer.emo import EmoLocalQueue, EmoPlaybackState, EmoSessionQueue
```

**Step 5: Run tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.base.test_emo_ws_store tests.base.test_client_release_schema tests.frontend.test_client_releases
```

Expected: PASS.

**Step 6: Commit**

```bash
git add supysonic/db_layer/emo.py supysonic/db_layer/client_releases.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: extract low dependency db models"
```

---

### Task 7: Extract Main Model Groups

**Files:**
- Create: `supysonic/db_layer/library.py`
- Create: `supysonic/db_layer/users.py`
- Create: `supysonic/db_layer/annotations.py`
- Create: `supysonic/db_layer/playlists.py`
- Create: `supysonic/db_layer/review_tasks.py`
- Create: `supysonic/db_layer/misc.py`
- Modify: `supysonic/db.py`
- Test: broad API/frontend/scanner tests listed below.

**Step 1: Move model groups in this exact order**

Move `User`, `User_Play_Activity`, and `ClientPrefs` to `users.py` only after confirming `Track` can be imported without cycles.

Move core library models to `library.py`:

```python
Image
Folder
Artist
Album
AlbumArtist
Track
TrackArtist
```

Move annotation factories and generated classes to `annotations.py`:

```python
_make_starred_model
StarredFolder
StarredArtist
StarredAlbum
StarredTrack
_make_rating_model
RatingFolder
RatingTrack
```

Move review models to `review_tasks.py`:

```python
ReviewTask
AlbumReviewTask
```

Move playlists to `playlists.py`:

```python
Playlist
SharedTrackLink
```

Move misc models to `misc.py`:

```python
ChatMessage
RadioStation
```

**Step 2: Keep `db.py` as facade**

After moving, `supysonic/db.py` should mainly contain imports and re-exports:

```python
from .db_layer.annotations import RatingFolder, RatingTrack, StarredAlbum, StarredArtist, StarredFolder, StarredTrack
from .db_layer.client_releases import ClientRelease
from .db_layer.core import Meta, PathMixin, PrimaryKeyField, db, now, random
from .db_layer.emo import EmoLocalQueue, EmoPlaybackState, EmoSessionQueue
from .db_layer.library import Album, AlbumArtist, Artist, Folder, Image, Track, TrackArtist
from .db_layer.misc import ChatMessage, RadioStation
from .db_layer.playlists import Playlist, SharedTrackLink
from .db_layer.review_tasks import AlbumReviewTask, ReviewTask
from .db_layer.runtime import close_connection, init_database, open_connection, release_database
from .db_layer.schema import SCHEMA_VERSION, execute_sql_resource_script
from .db_layer.users import ClientPrefs, User, User_Play_Activity
```

**Step 3: Resolve circular imports conservatively**

If a model method needs another model group, use local imports inside the method. Example:

```python
@classmethod
def prune(cls):
    from .annotations import StarredArtist
    from .library import Album, AlbumArtist, Track, TrackArtist

    ...
```

Do not introduce registries or dependency injection for this refactor.

**Step 4: Run broad tests**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_db_layer_contract tests.base.test_db tests.base.test_scanner tests.base.test_scanner_helpers tests.api.test_browse tests.api.test_media tests.api.test_playlist tests.api.test_annotation tests.frontend.test_playlist tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions
```

Expected: PASS.

**Step 5: Commit**

```bash
git add supysonic/db_layer/*.py supysonic/db.py tests/base/test_db_layer_contract.py
git commit -m "refactor: split db models by domain"
```

---

### Task 8: Final Verification and Cleanup

**Files:**
- Modify only if previous tasks left unused imports or dead code.

**Step 1: Run full unit test suite**

Run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest
```

Expected: `OK`.

**Step 2: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

**Step 3: Inspect final facade**

Run:

```bash
git diff -- supysonic/db.py supysonic/db_layer
```

Expected: `supysonic/db.py` is a compatibility facade, while extracted modules contain the moved implementation.

**Step 4: Commit any cleanup**

Only commit if cleanup changes were needed:

```bash
git add supysonic/db.py supysonic/db_layer tests/base/test_db_layer_contract.py
git commit -m "refactor: clean up db layer facade"
```

---

## Suggested Execution Scope

For the first refactor PR, stop after Task 5. That gives clear value by extracting core/runtime/schema/serializers while avoiding the highest-risk model split.

Do Task 6 and Task 7 in a separate PR after the first PR is green and merged.

## Required Final Verification

Before claiming the refactor is complete, run:

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest
git diff --check
```

Report the exact test count and result.
