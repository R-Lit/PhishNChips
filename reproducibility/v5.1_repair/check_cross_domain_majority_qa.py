#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "dataset_v5" / "phishnchips_v5_dataset.csv"
DEFAULT_RESULTS = ROOT / "dataset_v5" / "benchmark_results_v5.csv"
DEFAULT_REPORT = ROOT / "audit" / "cross_domain_majority_qa_r1.md"
DEFAULT_FAILURES = ROOT / "audit" / "cross_domain_majority_qa_failures_r1.csv"


def sender_domain(from_addr: str) -> str:
    return from_addr.split("@", 1)[1].lower().strip() if "@" in from_addr else ""


def url_domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower().split("@")[-1]


def read_cross_domain_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row["phish_label"] != "0":
                continue
            if row["datasource"] != "cross_domain_expansion_v1":
                continue
            if row["url_category"] != "cross_domain_legitimate":
                continue
            email = json.loads(row["email_content"])
            row["_email"] = email
            row["_sender_domain"] = sender_domain(email.get("from", ""))
            row["_url_domain"] = url_domain(row["url_raw"])
            rows[row["id"]] = row
    return rows


def collect_results(path: Path, sample_ids: set[str], strategy: str) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row["sample_id"] in sample_ids and row["strategy"] == strategy:
                results[row["sample_id"]].append(row)
    return results


def is_safe_prediction(value: str) -> bool:
    return value in {"1", "1.0"}


def summarize(rows: dict[str, dict], results: dict[str, list[dict]], min_safe: int) -> tuple[list[dict], Counter, Counter]:
    failures: list[dict] = []
    safe_dist: Counter = Counter()
    category_failures: Counter = Counter()

    for sample_id, row in sorted(rows.items()):
        sample_results = results.get(sample_id, [])
        safe_count = sum(1 for r in sample_results if is_safe_prediction(r["prediction"]))
        total_count = len(sample_results)
        safe_dist[safe_count] += 1
        category = row["strategy"] or "uncategorized"
        domain_mismatch = row["_sender_domain"] != row["_url_domain"]
        failed = total_count != 11 or safe_count < min_safe or not domain_mismatch
        if failed:
            category_failures[category] += 1
            email = row["_email"]
            failures.append(
                {
                    "id": sample_id,
                    "category": category,
                    "safe_count": safe_count,
                    "total_count": total_count,
                    "subject": email.get("subject", ""),
                    "from": email.get("from", ""),
                    "url_raw": row["url_raw"],
                    "sender_domain": row["_sender_domain"],
                    "url_domain": row["_url_domain"],
                    "domain_mismatch": str(domain_mismatch),
                    "body": email.get("body", "").replace("\r\n", "\n"),
                }
            )

    return failures, safe_dist, category_failures


def write_failures(path: Path, failures: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "category",
        "safe_count",
        "total_count",
        "subject",
        "from",
        "url_raw",
        "sender_domain",
        "url_domain",
        "domain_mismatch",
        "body",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failures)


def write_report(
    path: Path,
    *,
    strategy: str,
    rows: dict[str, dict],
    failures: list[dict],
    safe_dist: Counter,
    category_failures: Counter,
    min_safe: int,
    failures_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pass_count = len(rows) - len(failures)
    pass_rate = pass_count / len(rows) if rows else 0.0
    category_counts = Counter((row["strategy"] or "uncategorized") for row in rows.values())

    lines = [
        "# Cross-Domain Legitimate Majority QA",
        "",
        "Date: 2026-04-06",
        "",
        "## QA Definition",
        "",
        f"- Scope: `datasource=cross_domain_expansion_v1`, `url_category=cross_domain_legitimate`, `phish_label=0`.",
        f"- Strategy checked: `{strategy}`.",
        "- Safe prediction definition: `prediction=1` or `prediction=1.0`.",
        f"- Pass criterion: at least `{min_safe}` safe predictions out of 11 model predictions.",
        "- Domain check: sender domain must differ from URL domain.",
        "",
        "This is a neutral-prompt QA gate. It should not be confused with the benchmark's intentional false-positive stress test under stricter prompts such as `security_first`, `sender_url_match`, `trap_sender_match`, `trap_aggressive`, or `infra_aware`.",
        "",
        "## Result",
        "",
        f"- Samples checked: `{len(rows)}`",
        f"- Passed: `{pass_count}`",
        f"- Failed: `{len(failures)}`",
        f"- Pass rate: `{pass_rate:.1%}`",
        f"- Failure CSV: `{failures_path}`",
        "",
        "## Safe-Prediction Distribution",
        "",
        "| Safe predictions out of 11 | Sample count |",
        "|---:|---:|",
    ]
    for safe_count in range(12):
        lines.append(f"| {safe_count} | {safe_dist.get(safe_count, 0)} |")

    lines.extend(
        [
            "",
            "## Failures By Category",
            "",
            "| Category | Total | Failed |",
            "|---|---:|---:|",
        ]
    )
    for category in sorted(category_counts):
        lines.append(f"| `{category}` | {category_counts[category]} | {category_failures.get(category, 0)} |")

    lines.extend(
        [
            "",
            "## First 20 Failing Samples",
            "",
            "| ID | Category | Safe / 11 | Subject | URL |",
            "|---|---|---:|---|---|",
        ]
    )
    for failure in failures[:20]:
        subject = failure["subject"].replace("|", "\\|")
        lines.append(
            f"| `{failure['id']}` | `{failure['category']}` | {failure['safe_count']} | {subject} | `{failure['url_raw']}` |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The current 333-example cross-domain legitimate split does not pass the neutral baseline majority-safe QA gate. This means the paper and datasheet should not claim that all v5 legitimate emails pass the majority approval standard until the failing cross-domain rows are repaired, replaced, and re-evaluated.",
            "",
            "Recommended repair: revise or replace the failing cross-domain examples to make the legitimate SaaS relationship explicit, remove urgency-like subjects, avoid finance/signature/security pretexts that resemble phishing, then rerun at least the baseline 11-model QA gate. If the rows remain in the core benchmark, rerun the full 10-strategy result grid for any changed sample ids before regenerating leaderboard metrics.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check majority-safe QA for v5 cross-domain legitimate rows.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--strategy", default="baseline")
    parser.add_argument("--min-safe", type=int, default=6)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    args = parser.parse_args()

    rows = read_cross_domain_rows(args.dataset)
    results = collect_results(args.results, set(rows), args.strategy)
    failures, safe_dist, category_failures = summarize(rows, results, args.min_safe)
    write_failures(args.failures, failures)
    write_report(
        args.report,
        strategy=args.strategy,
        rows=rows,
        failures=failures,
        safe_dist=safe_dist,
        category_failures=category_failures,
        min_safe=args.min_safe,
        failures_path=args.failures,
    )

    print(f"checked={len(rows)} passed={len(rows) - len(failures)} failed={len(failures)}")
    print(f"report={args.report}")
    print(f"failures={args.failures}")


if __name__ == "__main__":
    main()
