"""WSGI entry point for production deployment (gunicorn, uWSGI, etc.)"""
import sys
import os

# Ensure the web package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "web"))

from web.app import app  # noqa: E402  (import after sys.path mutation)

if __name__ == "__main__":
    app.run()
