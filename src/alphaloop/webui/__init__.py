"""
alphaloop.webui — packaged morning console plus optional v0.7 FastAPI API.

Overnight-lab workers and the loopback daemon serve static assets from
``alphaloop.webui.static``. Those paths must import without FastAPI.

``create_app`` is the v0.7 FastAPI compatibility surface. It is imported
lazily so installing ``alphaloop[dev]`` is enough for the morning
console. FastAPI is only required when a caller actually constructs the
JSON API.
"""
from __future__ import annotations

from typing import Any

__all__ = ["create_app"]


def create_app(*args: Any, **kwargs: Any):
    from .api import create_app as _create_app

    return _create_app(*args, **kwargs)
