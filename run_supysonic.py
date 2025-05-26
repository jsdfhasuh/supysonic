#!/usr/bin/env python3
from supysonic.web import create_application

app = create_application()
if __name__ == '__main__':    
    app.run(host='0.0.0.0')
