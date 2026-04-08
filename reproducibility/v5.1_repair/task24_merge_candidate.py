#!/usr/bin/env python3
"""Task 24 Step 3: Merge retry supplement into candidate final file.

Reads:
  - dataset_v5/benchmark_results_v5_qa_repaired.csv (existing merged)
  - dataset_v5/v5.1_fresh_retry_results_2026-04-07.csv (supplement)

Writes:
  - dataset_v5/benchmark_results_v5_qa_repaired_fresh_candidate.csv

Merge rule:
  - Key is (sample_id, strategy, model)
  - Supplement rows replace old rows for the same key
  - All other rows preserved
  - No duplicates allowed

Then validates:
  - 36,630 unique pairs for 333 repaired samples
  - 0 missing, 0 duplicates, 0 error rows
  - Baseline majority-safe ≥ 330/333
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

NEURIPS = Path(__file__).resolve().parents[1]

MERGED_RESULTS = NEURIPS / "dataset_v5" / "benchmark_results_v5_qa_repaired.csv"
SUPPLEMENT = NEURIPS / "dataset_v5" / "v5.1_fresh_retry_results_2026-04-07.csv"
CANDIDATE_OUT = NEURIPS / "dataset_v5" / "benchmark_results_v5_qa_repaired_fresh_candidate.csv"
CANDIDATES_CSV = NEURIPS / "dataset_v5" / "cross_domain_legit_repair_candidates.csv"
BLOCKER_REPORT = NEURIPS / "audit" / "v5.1_fresh_retry_blocker_2026-04-07.md"

FIELDNAMES = ["sample_id", "model", "strategy", "true_label", "prediction", "correct", "raw_response", "error"]


def main():
    print(f"Task 24 Step 3: Merge & Validate")
    print(f"  Started: {datetime.now().isoformat(timespec='seconds')}")

    # Load cross-domain repair sample IDs
    cd_samples = set()
    with CANDIDATES_CSV.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            cd_samples.add(row["id"])
    print(f"  Cross-domain repair samples: {len(cd_samples)}")

    # Load supplement
    supplement = {}
    with SUPPLEMENT.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["model"], row["strategy"])
            supplement[key] = row
    print(f"  Supplement rows loaded: {len(supplement)}")

    # Merge: read existing, replace with supplement where key matches
    merged = []
    replaced = 0
    with MERGED_RESULTS.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            key = (row["sample_id"], row["model"], row["strategy"])
            if key in supplement:
                merged.append(supplement[key])
                replaced += 1
            else:
                merged.append(row)
    print(f"  Total merged rows: {len(merged)}")
    print(f"  Replaced from supplement: {replaced}")

    # Write candidate file
    with CANDIDATE_OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in merged:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"  Wrote: {CANDIDATE_OUT}")

    # Validate
    print(f"\n  === VALIDATION ===")

    # Check unique pairs
    pairs = [(r["sample_id"], r["model"], r["strategy"]) for r in merged]
    unique = set(pairs)
    duplicates = len(pairs) - len(unique)
    print(f"  Total rows: {len(pairs)}")
    print(f"  Unique pairs: {len(unique)}")
    print(f"  Duplicate pairs: {duplicates}")

    # Check cross-domain coverage
    cd_pairs = [(s, m, st) for s, m, st in unique if s in cd_samples]
    print(f"  Cross-domain pairs: {len(cd_pairs)} / 36630")
    missing_cd = 36630 - len(cd_pairs)
    print(f"  Missing cross-domain pairs: {missing_cd}")

    # Check errors
    total_errors = 0
    cd_errors = 0
    error_by_model = Counter()
    error_by_strategy = Counter()
    for row in merged:
        if row.get("error", "").strip():
            total_errors += 1
            if row["sample_id"] in cd_samples:
                cd_errors += 1
                error_by_model[row["model"]] += 1
                error_by_strategy[row["strategy"]] += 1
    print(f"  Total error rows: {total_errors}")
    print(f"  Cross-domain error rows: {cd_errors}")

    # Baseline majority-safe
    baseline_by_sample = defaultdict(list)
    for row in merged:
        if row["strategy"] == "baseline" and row["sample_id"] in cd_samples:
            baseline_by_sample[row["sample_id"]].append(row)

    pass_count = 0
    fail_list = []
    for sample_id in sorted(cd_samples):
        rows = baseline_by_sample.get(sample_id, [])
        safe = sum(1 for r in rows if r.get("prediction", "") in ("1", "1.0"))
        if len(rows) == 11 and safe >= 6:
            pass_count += 1
        else:
            fail_list.append((sample_id, safe, len(rows)))
    print(f"  Baseline majority-safe: {pass_count} / 333")
    if fail_list:
        print(f"  Failures ({len(fail_list)}):")
        for sid, safe, total in fail_list:
            print(f"    {sid}: {safe}/11 safe ({total} rows)")

    # Overall verdict
    all_ok = (
        duplicates == 0
        and missing_cd == 0
        and cd_errors == 0
        and pass_count >= 330
    )
    print(f"\n  {'✅ CANDIDATE VALIDATES CLEAN' if all_ok else '❌ VALIDATION FAILED'}")

    if not all_ok:
        BLOCKER_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with BLOCKER_REPORT.open("w", encoding="utf-8") as f:
            f.write("# Task 24 Fresh Retry Blocker Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
            f.write(f"Duplicates: {duplicates}\n")
            f.write(f"Missing CD pairs: {missing_cd}\n")
            f.write(f"CD error rows: {cd_errors}\n")
            f.write(f"Baseline majority-safe: {pass_count}/333\n")
            if cd_errors > 0:
                f.write("\n## Errors by model\n\n")
                for m, c in error_by_model.most_common():
                    f.write(f"- `{m}`: {c}\n")
            if fail_list:
                f.write("\n## Baseline failures\n\n")
                for sid, safe, total in fail_list:
                    f.write(f"- `{sid}`: {safe}/11 safe\n")
        print(f"  Wrote blocker report: {BLOCKER_REPORT}")
    else:
        print(f"  Ready for Step 4 (replace final files)")


if __name__ == "__main__":
    main()
