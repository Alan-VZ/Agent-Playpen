"""Observed-outcome task state for optional guided baseline settlement."""

import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation


def successful_operation(outcome, result):
    if isinstance(outcome, dict):
        if outcome.get("ok") is not True:
            return False
        status = outcome.get("status")
        if status not in {None, "succeeded"}:
            return False
    if isinstance(result, str):
        if result.lower().startswith(("error:", "[error]", "fetch error")):
            return False
    return True


def decimal_result(value):
    if not isinstance(value, str):
        if isinstance(value, (int, float)):
            value = str(value)
        else:
            return None
    try:
        parsed = Decimal(value.strip())
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


class BaselineSettlementState:
    def __init__(self, task, documents):
        self.task = task
        self.documents = dict(documents)
        self.observed = set()
        self.calculation_results = set()

    def record(self, tool_name, arguments, result, outcome=None):
        success = successful_operation(outcome, result)

        if tool_name == "read_fixture" and isinstance(arguments, dict):
            name = arguments.get("name")
            if not isinstance(name, str) or name not in self.documents:
                return
            if self.task == "B01" and name == "orders.csv" and success:
                self.observed.add("fixture_read")
            if self.task == "B02" and success:
                self.observed.add(("source", name))
            if self.task == "B03" and success:
                self.observed.add(("file", name))
            if self.task == "B04":
                if name == "primary" and not success:
                    self.observed.add("primary_failure")
                elif name == "backup" and success:
                    self.observed.add("backup_read")
                elif name == "empty" and success:
                    self.observed.add("empty_read")
            if self.task == "B05" and success:
                self.observed.add(("source", name))
        elif tool_name == "calculator" and isinstance(arguments, dict) and success:
            expression = arguments.get("expression")
            if not isinstance(expression, str):
                return
            expression = expression.strip()
            if not expression or "**" in expression:
                return
            if not re.fullmatch(r"[0-9+\-*/%(). \t]+", expression):
                return
            value = decimal_result(result)
            if value is not None:
                self.calculation_results.add(value)
        elif tool_name == "write_artifact" and isinstance(arguments, dict) and success:
            if arguments.get("name") == "report.json":
                self.observed.add("report_artifact")

    def record_report(self, answer):
        if not isinstance(answer, str):
            return
        try:
            report = json.loads(answer.strip())
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(report, dict):
            return
        if self.task == "B02":
            citations = report.get("citations")
            if not isinstance(citations, dict):
                return
            for fact in ("opens", "closed", "loan_days"):
                citation = citations.get(fact)
                if not isinstance(citation, dict):
                    return
                source = citation.get("source")
                quote = citation.get("quote")
                if (
                    isinstance(source, str)
                    and isinstance(quote, str)
                    and source in self.documents
                    and quote in self.documents[source]
                ):
                    self.observed.add(("quote", fact))
            if all(("quote", fact) in self.observed for fact in ("opens", "closed", "loan_days")):
                self.observed.add("report_evidence")
        elif self.task == "B05":
            source = report.get("source")
            quote = report.get("quote")
            reason = report.get("rejected_reason")
            if (
                source == "authority"
                and isinstance(quote, str)
                and quote in self.documents.get("authority", "")
                and isinstance(reason, str)
                and "12" in reason
                and "10" in reason
            ):
                self.observed.add("constraint_reason")

    def _b01_required_values(self):
        text = self.documents.get("orders.csv")
        if not isinstance(text, str):
            return set()
        seen = set()
        category_totals = {"parts": Decimal("0"), "service": Decimal("0")}
        net = Decimal("0")
        try:
            for row in csv.DictReader(io.StringIO(text)):
                order_id = row["id"]
                status = row["status"]
                category = row["category"]
                amount = Decimal(row["amount"])
                if order_id in seen:
                    continue
                seen.add(order_id)
                if status == "cancelled":
                    continue
                if status == "refund":
                    net -= amount
                    if category in category_totals:
                        category_totals[category] -= amount
                elif status == "paid":
                    net += amount
                    if category in category_totals:
                        category_totals[category] += amount
        except (KeyError, InvalidOperation):
            return set()
        return {net, category_totals["parts"], category_totals["service"]}

    def ready(self):
        if self.task == "B01":
            return (
                "fixture_read" in self.observed
                and self._b01_required_values().issubset(self.calculation_results)
            )
        if self.task == "B02":
            return (
                all(("source", name) in self.observed for name in self.documents)
                and "report_evidence" in self.observed
            )
        if self.task == "B03":
            return all(("file", name) in self.observed for name in self.documents) and "report_artifact" in self.observed
        if self.task == "B04":
            return {"primary_failure", "backup_read", "empty_read"} <= self.observed
        if self.task == "B05":
            return (
                all(("source", name) in self.observed for name in self.documents)
                and "constraint_reason" in self.observed
            )
        return False

    def remaining(self):
        if self.ready():
            return []
        if self.task == "B01":
            missing = []
            if "fixture_read" not in self.observed:
                missing.append("orders.csv")
            required = self._b01_required_values()
            for value in sorted(required - self.calculation_results, key=str):
                missing.append("verified calculation result " + str(value))
            return missing
        if self.task == "B02":
            missing = sorted(name for name in self.documents if ("source", name) not in self.observed)
            if "report_evidence" not in self.observed:
                missing.append("exact observed citations")
            return missing
        if self.task == "B03":
            missing = sorted(name for name in self.documents if ("file", name) not in self.observed)
            if "report_artifact" not in self.observed:
                missing.append("report.json")
            return missing
        if self.task == "B04":
            missing = []
            if "primary_failure" not in self.observed:
                missing.append("primary failure")
            if "backup_read" not in self.observed:
                missing.append("backup")
            if "empty_read" not in self.observed:
                missing.append("empty")
            return missing
        if self.task == "B05":
            missing = sorted(name for name in self.documents if ("source", name) not in self.observed)
            if "constraint_reason" not in self.observed:
                missing.append("12 A/10 A constraint evidence")
            return missing
        return []
