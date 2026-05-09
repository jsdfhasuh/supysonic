import hashlib
import os
import re
from urllib.parse import urlparse
from uuid import uuid4

from werkzeug.utils import secure_filename

from .db import ClientRelease, now


ALLOWED_FILE_TYPES = {
    "android": {"apk"},
    "windows": {"exe", "msi", "zip"},
}
BUILD_NAME_RE = re.compile(r"^\d+\.\d+\.\d+$")
CHUNK_SIZE = 1024 * 1024


class ReleaseValidationError(ValueError):
    pass


def get_payload_value(data, *keys):
    for key in keys:
        value = data.get(key) if hasattr(data, "get") else None
        if value is not None and value != "":
            return value
    return None


def normalize_platform(platform):
    value = str(platform or "").strip().lower()
    if value not in ALLOWED_FILE_TYPES:
        raise ReleaseValidationError("Invalid platform")
    return value


def normalize_build_name(build_name):
    value = str(build_name or "").strip()
    if not BUILD_NAME_RE.match(value):
        raise ReleaseValidationError("Invalid buildName")
    return value


def normalize_build_number(build_number):
    try:
        value = int(build_number)
    except (TypeError, ValueError):
        raise ReleaseValidationError("Invalid buildNumber")
    if value <= 0:
        raise ReleaseValidationError("Invalid buildNumber")
    return value


def infer_file_type(source):
    path = urlparse(str(source or "")).path
    extension = os.path.splitext(path)[1].lower().lstrip(".")
    if not extension:
        raise ReleaseValidationError("Missing file type")
    return extension


def normalize_file_type(platform, file_type, source=None):
    value = str(file_type or "").strip().lower().lstrip(".")
    if not value and source:
        value = infer_file_type(source)
    if value not in ALLOWED_FILE_TYPES[platform]:
        raise ReleaseValidationError(f"Invalid file type for {platform}")
    return value


def validate_external_url(download_url):
    value = str(download_url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ReleaseValidationError("Invalid downloadUrl")
    return value


def get_release_metadata(data):
    platform = normalize_platform(get_payload_value(data, "platform"))
    build_name = normalize_build_name(get_payload_value(data, "buildName", "build_name"))
    build_number = normalize_build_number(get_payload_value(data, "buildNumber", "build_number"))
    release_notes = get_payload_value(data, "releaseNotes", "release_notes")
    return platform, build_name, build_number, release_notes


def get_version(build_name, build_number):
    return f"{build_name}+{build_number}"


def get_build_key(release):
    return tuple(int(part) for part in release.build_name.split(".")), release.build_number


def get_latest_release(platform):
    platform = normalize_platform(platform)
    releases = list(
        ClientRelease.select().where(
            (ClientRelease.platform == platform) & (ClientRelease.active == True)
        )
    )
    if not releases:
        return None
    return max(releases, key=get_build_key)


def list_releases(platform):
    platform = normalize_platform(platform)
    releases = list(
        ClientRelease.select().where(
            (ClientRelease.platform == platform) & (ClientRelease.active == True)
        )
    )
    return sorted(releases, key=get_build_key, reverse=True)


def publish_external_release(data):
    platform, build_name, build_number, release_notes = get_release_metadata(data)
    download_url = validate_external_url(get_payload_value(data, "downloadUrl", "download_url"))
    file_type = normalize_file_type(
        platform,
        get_payload_value(data, "fileType", "file_type"),
        download_url,
    )
    file_name = os.path.basename(urlparse(download_url).path) or None
    return upsert_release(
        platform=platform,
        file_type=file_type,
        build_name=build_name,
        build_number=build_number,
        publish_mode="external_url",
        file_name=file_name,
        file_path=None,
        download_url=download_url,
        file_size=None,
        sha256=None,
        release_notes=release_notes,
    )


def publish_uploaded_release(data, file_storage, upload_dir, max_upload_size):
    if not file_storage or not file_storage.filename:
        raise ReleaseValidationError("Missing upload file")
    if not upload_dir:
        raise ReleaseValidationError("Release upload directory is not configured")

    platform, build_name, build_number, release_notes = get_release_metadata(data)
    inferred_type = infer_file_type(file_storage.filename)
    file_type = normalize_file_type(
        platform,
        get_payload_value(data, "fileType", "file_type") or inferred_type,
    )
    if file_type != inferred_type:
        raise ReleaseValidationError("Invalid file type for uploaded filename")

    version = get_version(build_name, build_number)
    original_name = secure_filename(file_storage.filename)
    if not original_name:
        original_name = f"{platform}-{version.replace('+', '-')}.{file_type}"
    target_dir = os.path.abspath(os.path.join(upload_dir, platform))
    os.makedirs(target_dir, exist_ok=True)
    target_name = f"{version.replace('+', '-')}-{uuid4().hex}-{original_name}"
    target_path = os.path.abspath(os.path.join(target_dir, target_name))
    upload_root = os.path.abspath(upload_dir)
    if os.path.commonpath([upload_root, target_path]) != upload_root:
        raise ReleaseValidationError("Invalid upload path")

    file_size, checksum = save_upload(file_storage, target_path, max_upload_size)
    return upsert_release(
        platform=platform,
        file_type=file_type,
        build_name=build_name,
        build_number=build_number,
        publish_mode="upload",
        file_name=original_name,
        file_path=target_path,
        download_url=None,
        file_size=file_size,
        sha256=checksum,
        release_notes=release_notes,
    )


def save_upload(file_storage, target_path, max_upload_size):
    try:
        limit = int(max_upload_size or 0)
    except (TypeError, ValueError):
        raise ReleaseValidationError("Invalid maximum upload size")
    hasher = hashlib.sha256()
    file_size = 0
    try:
        with open(target_path, "wb") as output:
            while True:
                chunk = file_storage.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)
                if limit and file_size > limit:
                    raise ReleaseValidationError("Upload exceeds maximum size")
                hasher.update(chunk)
                output.write(chunk)
    except Exception:
        if os.path.exists(target_path):
            os.remove(target_path)
        raise

    if file_size == 0:
        os.remove(target_path)
        raise ReleaseValidationError("Upload file is empty")
    return file_size, hasher.hexdigest()


def upsert_release(
    platform,
    file_type,
    build_name,
    build_number,
    publish_mode,
    file_name,
    file_path,
    download_url,
    file_size,
    sha256,
    release_notes,
):
    version = get_version(build_name, build_number)
    release = ClientRelease.get_or_none(
        (ClientRelease.platform == platform)
        & (ClientRelease.build_name == build_name)
        & (ClientRelease.build_number == build_number)
    )
    is_new = release is None
    old_file_path = None
    if is_new:
        release = ClientRelease(
            platform=platform,
            build_name=build_name,
            build_number=build_number,
            created=now(),
        )
    elif release.publish_mode == "upload":
        old_file_path = release.file_path

    release.file_type = file_type
    release.version = version
    release.publish_mode = publish_mode
    release.file_name = file_name
    release.file_path = file_path
    release.download_url = download_url
    release.file_size = file_size
    release.sha256 = sha256
    release.release_notes = release_notes
    release.active = True
    release.save(force_insert=is_new)
    if old_file_path and old_file_path != file_path and os.path.isfile(old_file_path):
        os.remove(old_file_path)
    return release


def serialize_release(release, download_url):
    return {
        "id": str(release.id),
        "platform": release.platform,
        "fileType": release.file_type,
        "buildName": release.build_name,
        "buildNumber": release.build_number,
        "version": release.version,
        "publishMode": release.publish_mode,
        "fileName": release.file_name,
        "fileSize": release.file_size,
        "sha256": release.sha256,
        "releaseNotes": release.release_notes,
        "downloadUrl": download_url,
        "sourceDownloadUrl": release.download_url,
        "created": release.created.isoformat() if release.created else None,
        "updated": release.updated.isoformat() if release.updated else None,
    }
