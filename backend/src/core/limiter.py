"""Rate limiter (slowapi), keyed by the client IP normalized by nginx."""

from slowapi import Limiter

from src.utils.http import get_client_ip

limiter = Limiter(key_func=get_client_ip)
