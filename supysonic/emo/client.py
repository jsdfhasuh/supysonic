import logging
import os
import time
from functools import wraps

from flask import jsonify, redirect, render_template, request, send_file, url_for

from . import api_routing
from .exceptions import GenericError
Version = "1.0.0"

logger = logging.getLogger(__name__)


def admin_only(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if not getattr(request, "user", None) or not request.user.admin:
            return redirect(url_for("frontend.index"))
        return f(*args, **kwargs)

    return decorated_func

@api_routing('/getVersion')
def get_version():
    return request.formatter("version", Version)


UPLOAD_FOLDER = './logs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_log_path(filename):
    if not filename:
        raise GenericError("Missing filename")

    basePath = os.path.abspath(UPLOAD_FOLDER)
    safePath = os.path.abspath(os.path.join(basePath, filename))
    if os.path.commonpath([basePath, safePath]) != basePath or not os.path.isfile(safePath):
        raise GenericError("File not found")

    return safePath


def getRequestSummary():
    return {
        'method': request.method,
        'path': request.path,
        'remote_addr': request.remote_addr,
        'content_type': request.content_type,
        'content_length': request.content_length,
        'args': request.args.to_dict(flat=False),
        'form_keys': sorted(request.form.keys()),
        'file_keys': sorted(request.files.keys()),
        'user_agent': request.user_agent.string,
    }

@api_routing('/upload_log')
def upload_log():
    # 检查 HTTP 请求中是否有 "file"
    if 'file' not in request.files:
        logger.warning(
            "Upload log failed: no file part; request=%s",
            getRequestSummary(),
        )
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning(
            "Upload log failed: empty filename; request=%s",
            getRequestSummary(),
        )
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    filename = time.strftime("%Y%m%d_%H%M%S_") + file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        file.save(file_path)
        return jsonify({'status': 'success', 'message': 'File uploaded successfully', 'path': file_path})
    except Exception as e:
        logger.exception(
            "Upload log failed while saving file '%s' to '%s'; request=%s",
            file.filename,
            file_path,
            getRequestSummary(),
        )
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 日志列表页面
@api_routing('/logs')
@admin_only
def list_logs():
    files = sorted(os.listdir(UPLOAD_FOLDER), reverse=True)
    return render_template('log_list.html', files=files)

# 查看日志页面
@api_routing('/viewlog')
@admin_only
def view_log():
    filename = request.args.get('filename')
    try:
        safePath = get_log_path(filename)
    except GenericError:
        return "File not found", 404
    
    try:
        with open(safePath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}", 500
    
    return render_template('view.html', filename=filename, content=content)


@api_routing('/downloadlog')
@admin_only
def download_log():
    filename = request.args.get('filename')
    try:
        safePath = get_log_path(filename)
    except GenericError:
        return "File not found", 404

    return send_file(safePath, as_attachment=True, download_name=os.path.basename(safePath))
