"""Render real maintenance templates for the optional Node/jsdom smoke test."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from debugging.dashboard.maintenance import CATALOG

root = Path(__file__).resolve().parents[1]
environment = Environment(loader=FileSystemLoader(root / "debugging/dashboard/templates"), autoescape=select_autoescape())
target = root / ".test-tmp"
target.mkdir(exist_ok=True)
for name in ("maintenance", "maintenance_callback"):
    html = environment.get_template(name + ".html").render(session_token="test-session-token", providers=list(CATALOG.values()))
    (target / (name + ".html")).write_text(html, encoding="utf-8")
print("Maintenance templates rendered with fake session data.")
