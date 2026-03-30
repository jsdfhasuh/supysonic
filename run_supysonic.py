#!/usr/bin/env python3
from supysonic.web import create_application
from supysonic.emo.ws import socketio


app = create_application()


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
