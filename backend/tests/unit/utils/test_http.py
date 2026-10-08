"""Regression coverage for the forwarded-header trust boundary."""

from ipaddress import ip_network

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from src.core.settings import AppSettings, get_settings
from src.utils.http import get_client_ip


@pytest.mark.parametrize(
    ("peer", "trusted", "headers", "expected"),
    [
        ("198.51.100.8", [], [("x-forwarded-for", "203.0.113.1")], "198.51.100.8"),
        ("198.51.100.8", ["10.0.0.0/24"], [("x-real-ip", "203.0.113.1")], "198.51.100.8"),
        ("10.0.0.2", ["10.0.0.2"], [("x-forwarded-for", "203.0.113.1, 198.51.100.8")], "198.51.100.8"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "203.0.113.1, 198.51.100.8, 10.0.0.3")], "198.51.100.8"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "10.0.0.3")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-real-ip", "198.51.100.8")], "198.51.100.8"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "invalid, 198.51.100.8"), ("x-real-ip", "192.0.2.1")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", ""), ("x-real-ip", "192.0.2.1")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "198.51.100.8,")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "198.51.100.8:80")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-real-ip", "invalid")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-real-ip", "198.51.100.8"), ("x-real-ip", "203.0.113.1")], "10.0.0.2"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "203.0.113.1"), ("x-forwarded-for", "198.51.100.8, 10.0.0.3")], "198.51.100.8"),
        ("2001:db8::2", ["2001:db8::/64"], [("x-forwarded-for", "2001:db8:1::8, 2001:db8::3")], "2001:db8:1::8"),
        ("2001:db8:1::8", [], [], "2001:db8:1::8"),
        ("::ffff:10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "::ffff:198.51.100.8")], "198.51.100.8"),
        ("10.0.0.2", ["10.0.0.0/24"], [("x-forwarded-for", "fe80::1%eth0")], "10.0.0.2"),
        (None, ["10.0.0.0/24"], [("x-forwarded-for", "198.51.100.8")], "unknown"),
        ("invalid-peer", ["10.0.0.0/24"], [("x-forwarded-for", "198.51.100.8")], "unknown"),
    ],
)
def test_client_ip_respects_trusted_proxy_boundary(peer, trusted, headers, expected, monkeypatch):
    monkeypatch.setattr(get_settings().app, "trusted_proxies", tuple(map(ip_network, trusted)))
    request = Request({
        "type": "http",
        "client": (peer, 12345) if peer is not None else None,
        "headers": [(name.encode(), value.encode()) for name, value in headers],
    })

    assert get_client_ip(request) == expected


def test_trusted_proxies_accept_ip_and_cidr_json_configuration(monkeypatch):
    monkeypatch.setenv("APP_TRUSTED_PROXIES", '["127.0.0.1", "10.0.0.0/24", "::1"]')
    settings = AppSettings(_env_file=None)

    assert settings.trusted_proxies == tuple(map(ip_network, ("127.0.0.1", "10.0.0.0/24", "::1")))


def test_trusted_proxies_default_to_none(monkeypatch):
    monkeypatch.delenv("APP_TRUSTED_PROXIES", raising=False)
    assert AppSettings(_env_file=None).trusted_proxies == ()


def test_invalid_trusted_proxy_configuration_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_TRUSTED_PROXIES", '["not-an-ip"]')
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None)
