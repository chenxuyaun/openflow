$ErrorActionPreference = "Stop"

python -m uvicorn openflow.app:app --app-dir src --reload --port 8001
