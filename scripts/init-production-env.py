"""Create a private production template with fresh secrets, without printing them."""

import os
from pathlib import Path
import secrets


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env.production"
    template = (root / ".env.production.example").read_text(encoding="utf-8")
    for name in ("POSTGRES_PASSWORD", "STATS_SECRET", "ADMIN_PASSWORD", "REVALIDATE_SECRET"):
        template = template.replace(f"{name}=\n", f"{name}={secrets.token_urlsafe(36)}\n")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(template)
    print("Created .env.production. Set hostname, contact and SMTP before deployment.")


if __name__ == "__main__":
    main()
