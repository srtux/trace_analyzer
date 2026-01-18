#!/bin/bash
set -e

# Start SRE Agent Unified Service (FastAPI + Static Frontend)
# It listens on $PORT (defaults to 8080 in Cloud Run)
echo "🚀 Starting Unified SRE Agent on port $PORT..."

# Inject Google Client ID if present
if [ ! -z "$GOOGLE_CLIENT_ID" ]; then
    echo "🔑 Injecting Google Client ID into web/index.html..."
    sed -i "s/\$GOOGLE_CLIENT_ID/$GOOGLE_CLIENT_ID/" web/index.html
fi
python server.py
