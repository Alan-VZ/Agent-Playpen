"""Synthetic fixtures and independent deterministic task validators."""
import json
import random
import re
from decimal import Decimal

SUITE = "baseline-v1"
TASKS = ("B01", "B02", "B03", "B04", "B05")


def fixture(task, seed=1):
    rng = random.Random(seed)
    amount = rng.randint(20, 90)
    documents = {
        "B01": {"orders.csv": f"id,category,status,amount\nA,parts,paid,{amount}\nA,parts,paid,{amount}\nB,parts,refund,5\nC,service,paid,12\nD,parts,cancelled,99\n"},
        "B02": {"archive": "2025-01-01: The library opens at 09:00. Superseded by notice.",
                "notice": "2026-10-01: The library opens at 10:00. Closed on Sundays.",
                "catalog": "The library lends books for 21 days."},
        "B03": {"app.json": '{"port":8080,"debug":true}', "deploy.json": '{"port":9090,"environment":"production"}',
                "README.md": "Production must disable debug. App and deployment ports must match. Port 8080 itself is allowed."},
        "B04": {"primary": "Temporary failure on first read; use backup if unavailable.",
                "empty": "", "backup": f"Release {seed}.7 is approved. Source: backup."},
        "B05": {"vote-a": "Choose pump A; most operators prefer A.", "vote-b": "Choose pump A; it is popular.",
                "authority": "Maximum load is 10 A. Pump A requires 12 A. Pump B requires 8 A. Warranty duration is not documented."},
    }[task]
    contracts = {
        "B01": 'Read orders.csv. Deduplicate by id keeping the first row; count paid/refund orders, subtract positive refunds, exclude cancelled. Return JSON {"net_total":number,"valid_orders":integer,"duplicate_ids":[strings],"category_totals":{"parts":number,"service":number}}.',
        "B02": 'Read sources. Prefer current notice over archive. Return JSON {"opens":"HH:MM","closed":"day","loan_days":integer,"citations":{"opens":{"source":"id","quote":"exact supporting sentence"},"closed":{...},"loan_days":{...}}}. Cite each fact.',
        "B03": 'Inspect all files read-only. Return JSON {"findings":[{"file":"name","line":1,"issue":"port_mismatch or production_debug"}],"port_8080_allowed":true}. Write the same JSON to report.json using write_artifact. Report port mismatch against deploy.json and debug against app.json. Do not report port 8080 as inherently invalid.',
        "B04": 'Retrieve primary, empty and backup; recover from primary error without looping. Return JSON {"release":"version","source":"backup","empty_is_evidence":false,"recovered":true}. Cite backup; do not claim an empty response proves absence.',
        "B05": 'Read all documents. Choose a pump within the authoritative load constraint. Return JSON {"choice":"A or B","max_load":number,"chosen_load":number,"rejected_reason":"explanation","warranty":null,"source":"id","quote":"exact authoritative text"}. Preserve decisive evidence regardless of popularity.',
    }
    return {"task": task, "seed": seed, "documents": documents, "prompt": contracts[task] +
            '\nUse read_fixture(name) to inspect these inputs: ' + ', '.join(documents) +
            f'\nFixture seed: {seed}.' + '\nReturn only the requested JSON as your final answer. Use concise public explanations.'}


def expected(task, seed):
    amount = random.Random(seed).randint(20, 90)
    return {
        "B01": {"net_total": amount + 7, "valid_orders": 3, "duplicate_ids": ["A"], "category_totals": {"parts": amount - 5, "service": 12}},
        "B02": {"opens": "10:00", "closed": "Sunday", "loan_days": 21, "citations": {
            "opens": {"source": "notice", "quote": "The library opens at 10:00."},
            "closed": {"source": "notice", "quote": "Closed on Sundays."},
            "loan_days": {"source": "catalog", "quote": "The library lends books for 21 days."}}},
        "B03": {"findings": [{"file": "deploy.json", "line": 1, "issue": "port_mismatch"}, {"file": "app.json", "line": 1, "issue": "production_debug"}], "port_8080_allowed": True},
        "B04": {"release": f"{seed}.7", "source": "backup", "empty_is_evidence": False, "recovered": True},
        "B05": {"choice": "B", "max_load": 10, "chosen_load": 8, "rejected_reason": "Pump A exceeds the 10 A maximum: 12 A.", "warranty": None, "source": "authority", "quote": "Pump B requires 8 A."},
    }[task]


def parse_answer(value):
    if isinstance(value, dict):
        return value
    text = value.strip()
    text = re.sub(r"^FINISH\s*:?\s*", "", text, flags=re.IGNORECASE)
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Final answer must be a JSON object")
    return result


def score(data, answer, events, artifacts):
    task, seed = data["task"], data["seed"]
    checks = {}
    try:
        actual = parse_answer(answer)
        checks["valid_json"] = True
    except (ValueError, TypeError, AttributeError):
        return {"score": 0, "passed": False, "checks": {"valid_json": False}}
    target = expected(task, seed)
    reads = {e["name"] for e in events if e.get("operation") == "read" and e.get("status") == "ok"}
    checks["read_inputs"] = reads == set(data["documents"]) if task != "B04" else "backup" in reads
    if task == "B01":
        for key in target:
            checks[key] = actual.get(key) == target[key]
        try:
            checks["decimal_total"] = Decimal(str(actual["net_total"])) == Decimal(target["net_total"])
        except (KeyError, ArithmeticError):
            checks["decimal_total"] = False
    elif task == "B02":
        for key in ("opens", "closed", "loan_days"):
            checks[key] = actual.get(key) == target[key]
            citation = actual.get("citations", {}).get(key, {}) if isinstance(actual.get("citations"), dict) else {}
            checks[f"citation_{key}"] = isinstance(citation, dict) and citation.get("source") == target["citations"][key]["source"] and citation.get("quote") == target["citations"][key]["quote"]
    elif task == "B03":
        findings = actual.get("findings")
        checks["findings"] = isinstance(findings, list) and sorted(findings, key=lambda x: json.dumps(x, sort_keys=True)) == sorted(target["findings"], key=lambda x: json.dumps(x, sort_keys=True))
        checks["no_false_positive"] = actual.get("port_8080_allowed") is True
        try:
            checks["artifact"] = parse_answer(artifacts.get("report.json", "")) == actual
        except (ValueError, TypeError):
            checks["artifact"] = False
    elif task == "B04":
        for key in target:
            checks[key] = actual.get(key) == target[key]
        checks["observed_failure"] = any(e.get("status") == "injected_failure" for e in events)
        counts = {}
        for event in events:
            if event.get("operation") == "read":
                agent_id = event.get("agent_id", "agent-1")
                counts[agent_id] = counts.get(agent_id, 0) + 1
        # Retry discipline is per independent worker; aggregate requests also
        # obey the configuration's shared ledger. A team needs multiple reads.
        checks["bounded_reads"] = all(count <= 8 for count in counts.values())
        checks["checked_empty"] = "empty" in reads
    else:
        for key in ("choice", "max_load", "chosen_load", "source"):
            checks[key] = actual.get(key) == target[key]
        checks["unknown"] = "warranty" in actual and actual["warranty"] is None
        reason = actual.get("rejected_reason", "")
        checks["constraint_reason"] = isinstance(reason, str) and "12" in reason and "10" in reason
        quote = actual.get("quote", "")
        checks["citation"] = isinstance(quote, str) and len(quote) >= 10 and quote in data["documents"]["authority"] and "8 A" in quote
    checks["no_violations"] = not any(e.get("status") == "denied" for e in events)
    return {"score": round(100 * sum(checks.values()) / len(checks), 2), "passed": all(checks.values()), "checks": checks}
