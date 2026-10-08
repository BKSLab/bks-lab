"""Rate limiter (slowapi), keyed by the client IP from forwarded headers."""

from slowapi import Limiter

from src.utils.http import get_client_ip

limiter = Limiter(key_func=get_client_ip)
