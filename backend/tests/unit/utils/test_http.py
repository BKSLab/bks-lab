"""Regression coverage for client IPs normalized by nginx."""

import pytest
from starlette.requests import Request

from src.utils.http import get_client_ip


@pytest.mark.parametrize(
    ("peer", "headers", "expected"),
    [
        ("198.51.100.8", [], "198.51.100.8"),
        ("10.0.0.2", [("x-real-ip", "198.51.100.8")], "198.51.100.8"),
        ("10.0.0.2", [("x-real-ip", " 198.51.100.8 ")], "198.51.100.8"),
        ("10.0.0.2", [("x-real-ip", "198.51.100.8"), ("x-forwarded-for", "203.0.113.1, 192.0.2.1")], "198.51.100.8"),
        ("10.0.0.2", [("x-forwarded-for", "198.51.100.8")], "10.0.0.2"),
        ("10.0.0.2", [("x-real-ip", "invalid"), ("x-forwarded-for", "198.51.100.8")], "10.0.0.2"),
        ("10.0.0.2", [("x-real-ip", "")], "10.0.0.2"),
        ("10.0.0.2", [("x-real-ip", "198.51.100.8, 203.0.113.1")], "10.0.0.2"),
        ("10.0.0.2", [("x-real-ip", "198.51.100.8:80")], "10.0.0.2"),
        ("10.0.0.2", [("x-real-ip", "198.51.100.8"), ("x-real-ip", "203.0.113.1")], "10.0.0.2"),
        ("2001:db8::2", [("x-real-ip", "2001:db8:1::8")], "2001:db8:1::8"),
        ("2001:db8:1::8", [], "2001:db8:1::8"),
        ("10.0.0.2", [("x-real-ip", "::ffff:198.51.100.8")], "198.51.100.8"),
        ("::ffff:198.51.100.8", [], "198.51.100.8"),
        ("10.0.0.2", [("x-real-ip", "fe80::1%eth0")], "10.0.0.2"),
        (None, [], "unknown"),
        ("invalid-peer", [], "unknown"),
    ],
)
def test_client_ip_uses_normalized_header_or_peer(
    peer: str | None, headers: list[tuple[str, str]], expected: str,
) -> None:
    request = Request({
        "type": "http",
        "client": (peer, 12345) if peer is not None else None,
        "headers": [(name.encode(), value.encode()) for name, value in headers],
    })

    assert get_client_ip(request) == expected
