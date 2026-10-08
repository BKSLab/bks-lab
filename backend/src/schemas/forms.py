"""Validated public form payloads without an optional email parser dependency."""

import re
from email.headerregistry import Address
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def normalize_email(value: str) -> str:
    """Validate a bare mailbox, reject header injection, normalize its identity."""
    value = value.strip()
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError("Enter a valid email address")
    try:
        address = Address(addr_spec=value)
        local = address.username
        domain = address.domain.encode("idna").decode("ascii").lower()
        if (
            not local or len(local) > 64 or not local.isascii()
            or not re.fullmatch(r"[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*", local)
            or "." not in domain or len(domain) > 253
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                   for part in domain.split("."))
            or value.count("@") != 1
        ):
            raise ValueError
    except (ValueError, IndexError, UnicodeError):
        raise ValueError("Enter a valid email address") from None
    normalized = f"{local.lower()}@{domain}"
    if len(normalized) > 254:
        raise ValueError("Enter a valid email address")
    return normalized


Email = Annotated[str, Field(min_length=3, max_length=254), AfterValidator(normalize_email)]


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: Email
    website: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        default="", max_length=2000, description="Leave empty."
    )


class FeedbackRequest(SubscribeRequest):
    name: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=10, max_length=5000)


class FeedbackResponse(BaseModel):
    status: Literal["sent"] = "sent"


class SubscribeResponse(BaseModel):
    status: Literal["subscribed"] = "subscribed"
