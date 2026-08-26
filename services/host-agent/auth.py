"""Bearer token verification for the host agent.

This module is the sole authority on authentication logic.  It has no knowledge
of HTTP routing, endpoint behaviour, or I/O; it can be tested in isolation
without any HTTP server dependency.
"""
from __future__ import annotations

import hmac
import logging

logger = logging.getLogger("host-agent")


def verify_bearer_token(authorization_header: str, expected_token: str) -> bool:
    """Return True iff *authorization_header* carries the correct Bearer token.

    Uses a constant-time comparison to prevent timing attacks.
    """
    if not authorization_header.startswith("Bearer "):
        return False
    received = authorization_header[len("Bearer "):]
    return hmac.compare_digest(received.encode(), expected_token.encode())
