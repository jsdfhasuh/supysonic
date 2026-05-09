import hmac
import os

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, send_file, session, url_for

from .. import DOWNLOAD_URL, VERSION
from ..client_releases import (
    ReleaseValidationError,
    get_latest_release,
    list_releases,
    normalize_platform,
    publish_external_release,
    publish_uploaded_release,
    serialize_release,
)
from ..db import ClientRelease, User
from ..managers.user import UserManager


client_releases = Blueprint("client_releases", __name__)


@client_releases.context_processor
def inject_metadata():
    return {
        "version": VERSION,
        "download_url": DOWNLOAD_URL,
    }


@client_releases.before_request
def attach_request_user():
    request.user = None
    if not session.get("userid"):
        return
    try:
        request.user = UserManager.get(session.get("userid"))
    except (TypeError, ValueError, User.DoesNotExist):
        request.user = None


def get_release_token():
    return str(current_app.config["WEBAPP"].get("release_api_token") or "")


def get_supplied_token():
    token = request.headers.get("X-Release-Token", "")
    if token:
        return token

    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def require_release_token():
    expected = get_release_token()
    if not expected:
        return jsonify({"error": "Release token is not configured"}), 503
    supplied = get_supplied_token()
    if not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Invalid release token"}), 403
    return None


def get_release_download_url(release):
    return url_for("client_releases.download_release", release_id=release.id)


def get_release_response(release):
    return serialize_release(release, get_release_download_url(release))


@client_releases.route("/latest")
def latest_release():
    platform = request.args.get("platform")
    try:
        release = get_latest_release(platform)
    except ReleaseValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    if release is None:
        return jsonify({"error": "No release available"}), 404
    return jsonify({"release": get_release_response(release)})


@client_releases.route("")
def release_index():
    platform = request.args.get("platform")
    try:
        releases = list_releases(platform)
    except ReleaseValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"releases": [get_release_response(release) for release in releases]})


@client_releases.route("/history")
def release_history():
    if not current_app.config["WEBAPP"].get("mount_webui", True):
        return jsonify({"error": "Client release history page requires the web UI"}), 404

    platform_labels = {"android": "Android", "windows": "Windows"}
    try:
        platform = normalize_platform(request.args.get("platform"))
        releases = list_releases(platform)
    except ReleaseValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return render_template(
        "client-release-history.html",
        platform=platform,
        platform_label=platform_labels[platform],
        releases=releases,
    )


@client_releases.route("/publish", methods=["POST"])
def publish_release():
    token_error = require_release_token()
    if token_error:
        return token_error

    try:
        if request.is_json:
            release = publish_external_release(request.get_json(silent=True) or {})
        else:
            release = publish_uploaded_release(
                request.form,
                request.files.get("file"),
                current_app.config["WEBAPP"].get("release_upload_dir"),
                current_app.config["WEBAPP"].get("release_max_upload_size"),
            )
    except ReleaseValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"release": get_release_response(release)})


@client_releases.route("/download/<release_id>")
def download_release(release_id):
    release = ClientRelease.get_or_none(
        (ClientRelease.id == release_id) & (ClientRelease.active == True)
    )
    if release is None:
        return jsonify({"error": "No release available"}), 404

    if release.publish_mode == "external_url":
        return redirect(release.download_url)

    if not release.file_path or not os.path.isfile(release.file_path):
        return jsonify({"error": "Release file is missing"}), 404
    return send_file(release.file_path, as_attachment=True)
