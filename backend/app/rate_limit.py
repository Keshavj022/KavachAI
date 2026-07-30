"""Shared slowapi rate limiter.

Defined in its own module so routes can import the ``limiter`` decorator and
``main`` can register the exception handler and middleware against the same
instance.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Keyed by client IP. Default limits are generous; sensitive endpoints
# (auth, detection) add stricter per-route limits.
limiter = Limiter(key_func=get_remote_address, default_limits=["240/minute"])
