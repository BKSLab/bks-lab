"""Local scheduler healthcheck without an HTTP listener or database credentials."""

import time
from pathlib import Path

from src.core.settings import get_settings


def is_healthy(path: Path, max_age_seconds: float) -> bool:
    """Check a pulse written only after a successful scheduler database refresh."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return 0 <= age <= max_age_seconds


def main() -> None:
    """Return a Docker-compatible healthcheck exit code."""
    settings = get_settings().news
    raise SystemExit(0 if is_healthy(settings.health_file, settings.health_max_age_seconds) else 1)


if __name__ == "__main__":
    main()
