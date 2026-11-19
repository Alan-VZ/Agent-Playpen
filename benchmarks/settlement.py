"""Task-state tracking for optional guided baseline settlement.

The controller records observed tool evidence; it never consults fixture
expected answers or injects those answers into model prompts.
"""


TASK_REQUIREMENTS = {
    "B01": ("fixture_read", "distinct_calculations"),
    "B02": ("required_sources",),
    "B03": ("required_files", "report_artifact"),
    "B04": ("primary_failure", "backup_read", "empty_read"),
    "B05": ("required_sources",),
}


class BaselineSettlementState:
    def __init__(self, task, documents):
        self.task = task
        self.documents = set(documents)
        self.observed = set()
        self.distinct_calculations = set()

    def record(self, tool_name, arguments, result):
        if tool_name == "read_fixture" and isinstance(arguments, dict):
            name = arguments.get("name")
            if isinstance(name, str) and name in self.documents:
                if self.task == "B01" and name == "orders.csv":
                    self.observed.add("fixture_read")
                if self.task == "B02":
                    self.observed.add(("source", name))
                if self.task == "B03":
                    self.observed.add(("file", name))
                if self.task == "B04":
                    if name == "primary":
                        if isinstance(result, str) and "[ERROR]" in result:
                            self.observed.add("primary_failure")
                    elif name == "backup":
                        self.observed.add("backup_read")
                    elif name == "empty":
                        self.observed.add("empty_read")
                if self.task == "B05":
                    self.observed.add(("source", name))
        elif tool_name == "calculator" and isinstance(arguments, dict):
            expression = arguments.get("expression")
            if isinstance(expression, str):
                normalized = "".join(expression.split())
                self.distinct_calculations.add(normalized)
                if len(self.distinct_calculations) >= 3:
                    self.observed.add("distinct_calculations")
        elif tool_name == "write_artifact" and isinstance(arguments, dict):
            if arguments.get("name") == "report.json":
                self.observed.add("report_artifact")

    def ready(self):
        if self.task == "B01":
            return "fixture_read" in self.observed and len(self.distinct_calculations) >= 3
        if self.task == "B02":
            return all(("source", name) in self.observed for name in self.documents)
        if self.task == "B03":
            return all(("file", name) in self.observed for name in self.documents) and "report_artifact" in self.observed
        if self.task == "B04":
            return {"primary_failure", "backup_read", "empty_read"} <= self.observed
        if self.task == "B05":
            return all(("source", name) in self.observed for name in self.documents)
        return False

    def remaining(self):
        if self.ready():
            return []
        if self.task == "B01":
            missing = []
            if "fixture_read" not in self.observed:
                missing.append("orders.csv")
            if "distinct_calculations" not in self.observed:
                missing.append("three distinct numeric calculations")
            return missing
        if self.task == "B02":
            return sorted(name for name in self.documents if ("source", name) not in self.observed)
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
            return sorted(name for name in self.documents if ("source", name) not in self.observed)
        return list(TASK_REQUIREMENTS.get(self.task, ()))
