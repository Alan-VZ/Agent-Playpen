"""CLI for versioned baseline experiments; no live requests without run/compare."""
import argparse
import json
from pathlib import Path
import uuid

from benchmarks.runner import ExperimentConfig, run_experiment
from benchmarks.report import render_report
from debugging.dashboard.readiness import preflight


def main():
    parser = argparse.ArgumentParser(description="Repeatable Agent Playpen baseline tests")
    parser.add_argument("action", choices=["run", "compare", "report"])
    parser.add_argument("--suite", choices=["baseline-v1"], default="baseline-v1")
    parser.add_argument("--config", "--configs", nargs="+", help="Paths or bundled names of non-secret experiment JSON configurations")
    parser.add_argument("--format", default="html,csv,json", help="Report formats: html,csv,json (all generated together)")
    parser.add_argument("--repeats", type=int, choices=[1, 5, 20], default=5)
    parser.add_argument("--tasks", nargs="+", choices=["B01", "B02", "B03", "B04", "B05"], help="Baseline tasks to run; default is all five")
    parser.add_argument("--output", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--experiment", help="Experiment directory for report")
    args = parser.parse_args()
    if args.action == "report":
        if not args.experiment:
            parser.error("--experiment is required for report")
        output = Path(args.experiment)
        if not output.exists():
            output = Path("benchmark-results") / args.experiment
        record = json.loads((output / "experiment.json").read_text(encoding="utf-8"))
    else:
        def config_path(name):
            path = Path(name)
            return path if path.is_file() else Path(__file__).parent / "configs" / (name + ".json")
        configs = [ExperimentConfig.model_validate(json.loads(config_path(p).read_text(encoding="utf-8"))) for p in args.config] if args.config else [ExperimentConfig()]
        root = Path(__file__).resolve().parents[1]
        for config in configs:
            readiness = preflight(root, config.model_dump())
            if not readiness["ready"]:
                for row in readiness["providers"]:
                    if row["provider"] in readiness["blocking"]:
                        print(f'{row["name"]}: {row["status"]}; {row["portal"]}; save with python -m config.credentials set {row["key_name"]}')
                raise SystemExit("Required credentials need setup. Open the dashboard API inventory.")
        output = Path(args.output or ("benchmark-results/" + uuid.uuid4().hex))
        record = run_experiment(configs, output, args.repeats, resume=args.resume, tasks=args.tasks,
                                on_progress=lambda p: print(f'{p["completed"]}/{p["scheduled"]} {p["task"]}: {p["status"]}') if "completed" in p else None)
    render_report(record, output)
    print(f'Report: {(output / "comparison.html").resolve()}')


if __name__ == "__main__":
    main()
