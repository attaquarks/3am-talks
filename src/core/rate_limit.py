"""
core/rate_limit.py — shared slowapi Limiter singleton.

Route modules import `limiter` from here and apply `@limiter.limit(...)`
decorators. `main.py` attaches this same instance to `app.state` and
registers the RateLimitExceeded handler.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
