#!/bin/bash
cd /workspaces/langgraph_workspace

# Load environment variables from .env file
set -a
source .env
set +a

# Run the server with PYTHONPATH set
export PYTHONPATH=.
python src/api/agent_server.py