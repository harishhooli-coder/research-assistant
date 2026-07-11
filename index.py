"""Vercel entrypoint — re-exports the FastAPI app from api.main."""

from api.main import app

__all__ = ["app"]
