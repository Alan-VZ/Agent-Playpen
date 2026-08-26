# Debug Dashboard

The debug dashboard is a FastAPI + Jinja2 web application that provides real-time visibility into agent traces, costs, and backend health. Launch with:

python -m debugging.dashboard.server --port 8765
Then open <http://localhost:8765> in your browser. The dashboard auto-refreshes every 5 seconds.

API Endpoints:

GET /traces — list all saved trace files in the traces directory
GET /traces/{session_id} — view a specific trace as formatted JSON
GET /cost — current session cost summary across all recorded models
GET /health — backend connectivity check, returns status for each configured backend
