"""Portable, escaped experiment reports from the same stored evidence."""
import csv
import html
import json
from pathlib import Path
from benchmarks.runner import summaries, atomic_json


def render_report(record, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = summaries(record)
    atomic_json(output / "summary.json", rows)
    fields = ["name", "agents", "B01", "B02", "B03", "B04", "B05", "passed", "attempted", "scheduled", "minimum_quality", "mean_quality", "median_seconds", "p95_seconds", "actual_tokens", "reserved_tokens", "tool_requests", "estimated_reserved_usd", "violations", "qualified"]
    flat = []
    for row in rows:
        flat.append({**{k: v for k, v in row.items() if k != "tasks"},
                     **{key: f'{value["passed"]}/{value["scheduled"]}' for key, value in row["tasks"].items()}})
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        # Spreadsheet formula injection protection for user-supplied configuration names.
        writer.writerows({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in row.items()} for row in flat)
    def esc(value):
        return html.escape("unknown" if value is None else str(value))
    table = '<table><thead><tr>' + ''.join(f'<th>{esc(f)}</th>' for f in fields) + '</tr></thead><tbody>'
    for row in flat:
        table += '<tr>' + ''.join(f'<td>{esc(row.get(f))}</td>' for f in fields) + '</tr>'
    table += '</tbody></table>'
    details = ''
    for attempt in record["attempts"]:
        label = f'{record["configs"][attempt["config_index"]]["name"]} · {attempt["task"]} · repeat {attempt["repetition"]+1} · {attempt["status"]}'
        details += f'<details><summary>{esc(label)}</summary><pre>{esc(json.dumps(attempt, indent=2))}</pre></details>'
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Agent Playpen baseline comparison</title><style>body{font:15px system-ui;margin:30px;background:#101827;color:#e5edf7}table{border-collapse:collapse;display:block;overflow:auto}td,th{padding:9px;border:1px solid #52627a;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{padding:10px;border-bottom:1px solid #52627a}</style><h1>Baseline comparison</h1><p>' + esc(record.get('evidence_type', 'model experiment')) + ' · ' + esc(record["suite"]) + ' · ' + esc(record["created_at"]) + ' · ' + esc(record["status"]) + '</p><p>Task cells show strict passes / scheduled attempts. Unknown usage is not zero. Costs are conservative declared-rate reservations, not invoices. Confidence intervals are in summary.json. Small samples do not establish general reliability. Frozen retrieval does not test live search quality.</p>' + table + '<h2>Attempt evidence</h2>' + details + '</html>'
    (output / "comparison.html").write_text(document, encoding="utf-8")
    return rows
