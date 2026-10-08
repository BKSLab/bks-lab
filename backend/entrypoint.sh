#!/bin/bash

set -e

echo "Applying migrations..."
alembic upgrade head

echo "Starting backend..."
exec "$@"
