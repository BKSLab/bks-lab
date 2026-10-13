"""Resolve client addresses from the header normalized by nginx."""

from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request


def _parse_address(value: str) -> IPv4Address | IPv6Address:
    """Parse bare IP addresses and canonicalize IPv4-mapped IPv6 peers."""
    if "%" in value:
        raise ValueError("Scoped IP addresses are not supported")
    address = ip_address(value.strip())
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def get_client_ip(request: Request) -> str:
    """Resolve a canonical client IP from nginx or the direct connection.

    Production traffic must enter through nginx, which overwrites X-Real-IP.
    The backend has no public port in production.

    Args:
        request: Incoming request.

    Returns:
        X-Real-IP when it contains a single valid address, otherwise the
        connection peer. Unknown peers share one rate-limit bucket.
    """
    real_headers = request.headers.getlist("x-real-ip")
    if len(real_headers) == 1:
        try:
            return str(_parse_address(real_headers[0]))
        except ValueError:
            pass
    try:
        return str(_parse_address(request.client.host)) if request.client else "unknown"
    except ValueError:
        return "unknown"
