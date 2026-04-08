#!/usr/bin/env bash
set -euo pipefail

# This runs only on first database initialization (empty PGDATA).
# At image build time, we must not write into $PGDATA because Docker copies image
# contents into a fresh named volume, making it "not empty" and breaking initdb.

echo "max_connections = 300" >> "${PGDATA}/postgresql.conf"

