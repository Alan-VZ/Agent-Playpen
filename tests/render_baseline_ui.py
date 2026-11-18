"""Render production templates with a fake token for DOM checks."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from benchmarks.tasks import task_catalog  # noqa: E402
environment = Environment(loader=FileSystemLoader(root / "debugging/dashboard/templates"), autoescape=select_autoescape())
target = root / ".test-tmp"
target.mkdir(exist_ok=True)
for name in ("api_inventory", "baselines", "index", "controlled_study", "scientific_calculator", "tools"):
    rendered = environment.get_template(name + ".html").render(study_id="a" * 32, session_token="test-session-token", backends=["lm_studio", "openrouter", "groq", "ollama", "openai", "azure_openai", "together", "anthropic"], planners=["react"], tools=["web_search", "fetch", "nimble_extract", "read_file", "write_file", "calculator", "scientific_calculator", "datetime"], baseline_tasks=task_catalog())
    (target / ("baseline_" + name + ".html")).write_text(rendered, encoding="utf-8")
print("Baseline and inventory production templates rendered with fake session data.")
