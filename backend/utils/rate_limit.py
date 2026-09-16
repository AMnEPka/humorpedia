"""Общий rate limiter (slowapi). Подключается в server.py через app.state.limiter и SlowAPIMiddleware."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["1000/minute"])
