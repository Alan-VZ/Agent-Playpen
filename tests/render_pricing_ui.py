"""Render the actual model-price page for the optional DOM smoke test."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from debugging.dashboard.model_pricing import OFFICIAL_URLS

root = Path(__file__).resolve().parents[1]
environment = Environment(loader=FileSystemLoader(root / "debugging/dashboard/templates"), autoescape=select_autoescape())
target = root / ".test-tmp/model_prices.html"
target.parent.mkdir(exist_ok=True)
target.write_text(environment.get_template("model_prices.html").render(session_token="test-session-token", backends=list(OFFICIAL_URLS)), encoding="utf-8")
print("Model-price template rendered with fake session data.")
