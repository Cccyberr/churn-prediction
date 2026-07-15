"""Lightweight basic-auth wrapper for admin-only routes."""
from __future__ import annotations

import secrets
from functools import wraps

from flask import Response, request

from app.config import config


def _check(user: str, password: str) -> bool:
    return secrets.compare_digest(user, config.admin_username) and secrets.compare_digest(
        password, config.admin_password
    )


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check(auth.username or "", auth.password or ""):
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="Admin"'},
            )
        return view(*args, **kwargs)

    return wrapped
