"""API contract tests for the editor image library (/api/admin/content/images)."""

from io import BytesIO

import pytest
from PIL import Image
from pydantic import SecretStr

from src.core.settings import get_settings

LOGIN = {"username": "test-admin", "password": "test-only-password"}
ORIGIN = {"Origin": "http://test"}


@pytest.fixture(autouse=True)
def admin_config(monkeypatch):
    settings = get_settings().admin
    monkeypatch.setattr(settings, "username", LOGIN["username"])
    monkeypatch.setattr(settings, "password", SecretStr(LOGIN["password"]))
    monkeypatch.setattr(settings, "allowed_origins", ("http://test",))
    monkeypatch.setattr(settings, "cookie_secure", False)


async def login(client) -> None:
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=ORIGIN)
    assert response.status_code == 200


def png_bytes(size: tuple[int, int] = (640, 480)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "blue").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("method", ["get", "post"])
async def test_image_endpoints_reject_anonymous_requests(client, method):
    response = await getattr(client, method)("/api/admin/content/images", headers=ORIGIN)

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


async def test_upload_rejects_untrusted_origin(client):
    await login(client)

    response = await client.post(
        "/api/admin/content/images",
        files={"file": ("cover.png", png_bytes(), "image/png")},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


async def test_upload_converts_and_lists_the_image(client):
    await login(client)

    uploaded = await client.post(
        "/api/admin/content/images",
        files={"file": ("My Cover.PNG", png_bytes(), "image/png")},
        data={"section": "articles"},
        headers=ORIGIN,
    )

    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["path"].startswith("/uploads/articles/my-cover-")
    assert body["path"].endswith(".webp")
    assert body["mime"] == "image/webp"
    assert body["width"] == 640 and body["height"] == 480

    listed = await client.get("/api/admin/content/images", headers=ORIGIN)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [body["id"]]

    # The stored file is served back by the app (dev mode static mount).
    served = await client.get(body["path"])
    assert served.status_code == 200
    assert served.content[:4] == b"RIFF"  # WebP container signature


async def test_upload_rejects_a_non_image_payload(client):
    await login(client)

    response = await client.post(
        "/api/admin/content/images",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
        headers=ORIGIN,
    )

    assert response.status_code == 422


async def test_upload_rejects_an_oversized_file(client):
    await login(client)
    limit = get_settings().media.max_bytes

    response = await client.post(
        "/api/admin/content/images",
        files={"file": ("huge.png", b"x" * (limit + 1), "image/png")},
        headers=ORIGIN,
    )

    assert response.status_code == 413


async def test_upload_rejects_an_unknown_section(client):
    await login(client)

    response = await client.post(
        "/api/admin/content/images",
        files={"file": ("cover.png", png_bytes(), "image/png")},
        data={"section": "../etc"},
        headers=ORIGIN,
    )

    assert response.status_code == 422
