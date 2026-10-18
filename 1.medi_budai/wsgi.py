#!/usr/bin/env python3
"""
WSGI entry point for MediBudAI application.
This file is used for production deployments with WSGI servers like Gunicorn, uWSGI, etc.
"""

import os
import sys
from dotenv import load_dotenv

# Add the application directory to Python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Import the Flask application
from app import app

# WSGI application callable
application = app

if __name__ == "__main__":
    # This allows running with python wsgi.py for testing
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', '5000'))
    )
