import argparse
import json
import sys

from .engine import CalculationError, QalculateEngine


def main():
    parser = argparse.ArgumentParser(
        description="Local high-precision Qalculate evaluation and scalar 2D plots"
    )
    parser.add_argument("operation", choices=["evaluate", "plot"])
    parser.add_argument("expression")
    parser.add_argument("--binary")
    parser.add_argument("--precision", type=int, default=50)
    parser.add_argument(
        "--variables",
        default="{}",
        help='JSON string of exact bindings, e.g. {"mass":"2 kg"}',
    )
    parser.add_argument(
        "--mode", choices=["approximate", "exact", "try exact"], default="approximate"
    )
    parser.add_argument(
        "--angle-unit", choices=["radians", "degrees"], default="radians"
    )
    parser.add_argument("--output-dir", default="qalculate-output")
    parser.add_argument("--work-dir")
    parser.add_argument("--x-min", default="-10")
    parser.add_argument("--x-max", default="10")
    parser.add_argument("--points", type=int, default=201)
    args = parser.parse_args()
    try:
        engine = QalculateEngine(args.binary, work_dir=args.work_dir)
        options = dict(
            variables=json.loads(args.variables),
            precision=args.precision,
            angle_unit=args.angle_unit,
        )
        result = (
            engine.evaluate(args.expression, mode=args.mode, **options)
            if args.operation == "evaluate"
            else engine.plot(
                args.expression,
                output_dir=args.output_dir,
                x_min=args.x_min,
                x_max=args.x_max,
                points=args.points,
                **options,
            )
        )
    except (CalculationError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": getattr(exc, "code", "invalid_request"),
                        "message": str(exc),
                    },
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
