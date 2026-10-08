"""Resolve client addresses across an explicitly trusted proxy boundary."""

from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request

from src.core.settings import get_settings


def _parse_address(value: str) -> IPv4Address | IPv6Address:
    """Parse bare IP addresses and canonicalize IPv4-mapped IPv6 peers."""
    if "%" in value:
        raise ValueError("Scoped IP addresses are not supported")
    address = ip_address(value.strip())
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def get_client_ip(request: Request) -> str:
    """Resolve a canonical client IP, trusting headers only from proxy peers.

    Args:
        request: Incoming request.

    Returns:
        The first untrusted address when walking X-Forwarded-For from the
        right, or X-Real-IP when X-Forwarded-For is absent. Invalid headers
        fall back to the peer; unknown peers share one rate-limit bucket.
    """
    try:
        peer = _parse_address(request.client.host) if request.client else None
    except ValueError:
        peer = None
    if peer is None:
        return "unknown"

    trusted_proxies = get_settings().app.trusted_proxies

    def is_trusted(address: IPv4Address | IPv6Address) -> bool:
        return any(address in network for network in trusted_proxies)

    if not is_trusted(peer):
        return str(peer)

    forwarded_headers = request.headers.getlist("x-forwarded-for")
    if forwarded_headers:
        try:
            chain = [_parse_address(value) for value in ",".join(forwarded_headers).split(",")]
        except ValueError:
            return str(peer)
        for address in reversed(chain):
            if not is_trusted(address):
                return str(address)
        return str(peer)

    real_headers = request.headers.getlist("x-real-ip")
    if len(real_headers) == 1:
        try:
            return str(_parse_address(real_headers[0]))
        except ValueError:
            pass
    return str(peer)
