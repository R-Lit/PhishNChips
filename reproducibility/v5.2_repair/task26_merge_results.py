#!/usr/bin/env python3
"""Task 26 Step 7: Merge results into candidate full results file.

Starts from dataset_v5/benchmark_results_v5_qa_repaired.csv,
drops the rows matching the 57 replaced IDs, limits insertion to the 6,270 new result rows
from dataset_v5/v5.2_replacement_results.csv, and checks for validation.
"""

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

NEURIPS = Path(__file__).resolve().parent.parent

OLD_RESULTS = NEURIPS / "dataset_v5" / "benchmark_results_v5_qa_repaired.csv"
NEW_RESULTS = NEURIPS / "dataset_v5" / "v5.2_replacement_results.csv"
REPLACEMENT_IDS_FILE = NEURIPS / "dataset_v5" / "v5.2_replacement_rows_candidate.csv"
MERGED_RESULTS = NEURIPS / "dataset_v5" / "benchmark_results_v5_v5.2_repaired.csv"

FIELDNAMES = ["sample_id", "model", "strategy", "true_label", "prediction", "correct", "raw_response", "error"]

def main():
    print("Task 26 Step 7: Merge into Candidate Full Results File")

    # Load replacement IDs
    rep_ids = set()
    with REPLACEMENT_IDS_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rep_ids.add(row["id"])
    print(f"  Replacement IDs: {len(rep_ids)}")

    # Load new results
    new_results_dict = {}
    with NEW_RESULTS.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            k = (row["sample_id"], row["model"], row["strategy"])
            new_results_dict[k] = row
    print(f"  New result rows: {len(new_results_dict)}")

    # Load old and merge
    merged_rows = []
    dropped_count = 0
    with OLD_RESULTS.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["sample_id"] in rep_ids:
                dropped_count += 1
            else:
                merged_rows.append(row)
    print(f"  Old rows kept: {len(merged_rows)}")
    print(f"  Old rows dropped: {dropped_count}")

    # Append new results
    for row in new_results_dict.values():
        merged_rows.append(row)

    print(f"  Total merged rows: {len(merged_rows)}")

    # Validate
    pairs = [(r["sample_id"], r["model"], r["strategy"]) for r in merged_rows]
    unique = set(pairs)
    errors = sum(1 for r in merged_rows if r.get("error", "").strip())
    
    print(f"\n  === Validation ===")
    print(f"  Total rows: {len(pairs)}")
    print(f"  Unique pairs: {len(unique)}")
    print(f"  Error rows: {errors}")

    if len(pairs) != len(unique) or errors > 0 or len(pairs) != 220000:
        print("  ❌ Validation failed!")
    else:
        print("  ✅ Validation passed!")

    # Write merged 
    with MERGED_RESULTS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in merged_rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"  Wrote: {MERGED_RESULTS}")

if __name__ == "__main__":
    main()
