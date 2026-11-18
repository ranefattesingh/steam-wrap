"""ASGI entrypoint.

Run with::

    uvicorn app:app --reload

The real application lives in the :mod:`steam_wrap` package; this module only
exposes the instance so process managers have a short, stable import path.
"""

from steam_wrap.main import create_app

app = create_app()
