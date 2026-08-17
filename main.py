"""
URL Shortener – Application Entry Point

This module is the ASGI entry point consumed by uvicorn / gunicorn.
It creates the FastAPI application via the factory in app.core.application.
"""

from app.core.application import create_application

app = create_application()
