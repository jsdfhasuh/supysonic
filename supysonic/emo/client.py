from . import api_routing
from .exceptions import GenericError
from flask import request
from flask import Flask, request, jsonify, render_template
import os,time
Version = "1.0.0"

@api_routing('/getVersion')
def get_version():
    return request.formatter("version", Version)


UPLOAD_FOLDER = './logs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@api_routing('/upload_log')
def upload_log():
    # 检查 HTTP 请求中是否有 "file"
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    filename = time.strftime("%Y%m%d_%H%M%S_") + file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        file.save(file_path)
        return jsonify({'status': 'success', 'message': 'File uploaded successfully', 'path': file_path})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 日志列表页面
@api_routing('/logs')
def list_logs():
    files = sorted(os.listdir(UPLOAD_FOLDER), reverse=True)
    return render_template('log_list.html', files=files)

# 查看日志页面
@api_routing('/viewlog')
def view_log():
    filename = request.args.get('filename')
    safe_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(safe_path):
        return "File not found", 404
    
    try:
        with open(safe_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}", 500
    
    return render_template('view.html', filename=filename, content=content)

