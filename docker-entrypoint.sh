#!/bin/sh
set -e

cd /app

# Ensure turn-detector and other plugin models are present (also run at image build).
.venv/bin/python src/agent.py download-files

# Use `start` in containers; `dev` watches files and is for local development only.
exec .venv/bin/python src/agent.py "${@:-start}"
