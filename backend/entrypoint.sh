#!/bin/bash

set -e

echo "Applying migrations..."
alembic upgrade head

echo "Seeding missing News Analyzer catalogue entries..."
python -m scripts.seed_news

echo "Starting backend..."
exec "$@"
