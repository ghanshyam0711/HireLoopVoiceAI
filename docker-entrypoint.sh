#!/bin/sh
set -e

cd /app

# Ensure turn-detector and other plugin models are present (also run at image build).
.venv/bin/python src/agent.py download-files

exec .venv/bin/python src/agent.py "${@:-dev}"
