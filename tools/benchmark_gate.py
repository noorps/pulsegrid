"""Check accepted readings, throughput and p95 against the benchmark budget."""

import argparse
import json
import math
import re
from pathlib import Path


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("threshold must be finite and positive")
    return number


def evaluate(text, minimum, maximum):
    patterns = {
        "accepted": r"accepted: (\d+)/(\d+)",
        "throughput": r"throughput: (\d+(?:\.\d+)?) events/sec",
        "p95_ms": r"p95 latency: (\d+(?:\.\d+)?) ms",
    }
    matches = {key: re.findall(f"^{pattern}$", text, re.MULTILINE)
               for key, pattern in patterns.items()}
    if any(len(values) != 1 for values in matches.values()):
        raise ValueError("expected exactly one accepted count, throughput, and p95 line")
    accepted, total = map(int, matches["accepted"][0])
    throughput = float(matches["throughput"][0])
    p95 = float(matches["p95_ms"][0])
    if not all(math.isfinite(value) for value in (throughput, p95)):
        raise ValueError("benchmark metrics must be finite")
    failures = []
    if accepted != 10000 or total != 10000:
        failures.append(f"accepted {accepted}/{total}; required 10000/10000")
    if throughput < minimum:
        failures.append(f"throughput {throughput} < {minimum} events/sec")
    if p95 > maximum:
        failures.append(f"p95 {p95} > {maximum} ms")
    return {"passed": not failures, "accepted": accepted, "total": total,
            "events_per_sec": throughput, "p95_ms": p95,
            "min_events_per_sec": minimum, "max_p95_ms": maximum,
            "failures": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--min-events-per-sec", type=positive_number, required=True)
    parser.add_argument("--max-p95-ms", type=positive_number, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(args.benchmark.read_text(), args.min_events_per_sec, args.max_p95_ms)
    except (OSError, ValueError) as exc:
        result = {"passed": False, "failures": [str(exc)]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
