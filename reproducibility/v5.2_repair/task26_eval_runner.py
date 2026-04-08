#!/usr/bin/env python3
"""Task 26 Step 6: Rerun model evaluations for 57 replaced rows.

57 rows x 10 strategies x 11 models = 6,270 result pairs.
Uses the same benchmark infrastructure as the main run.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

NEURIPS = Path(__file__).resolve().parents[1]
ROOT = NEURIPS.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from run_benchmark import Config, APIClient, PromptManager, Evaluator

DATASET_FILE = NEURIPS / "dataset_v5" / "phishnchips_v5_v5.2_repaired_dataset.csv"
REPLACEMENT_IDS_FILE = NEURIPS / "dataset_v5" / "v5.2_replacement_rows_candidate.csv"
RESULTS_OUT = NEURIPS / "dataset_v5" / "v5.2_replacement_results.csv"
CHECKPOINT_OUT = NEURIPS / "dataset_v5" / "v5.2_replacement_results_checkpoint.json"

FIELDNAMES = ["sample_id", "model", "strategy", "true_label", "prediction", "correct", "raw_response", "error"]
MAX_RETRIES = 3
MAX_WORKERS = 30

ALL_STRATEGIES = [
    "baseline", "security_first", "balanced", "efficiency_first",
    "helpful", "trust_context", "sender_url_match", "trap_sender_match",
    "trap_aggressive", "infra_aware",
]
ALL_MODELS = Config.MODELS  # 11 models


def load_dataset() -> dict[str, dict]:
    dataset = {}
    with DATASET_FILE.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            dataset[row["id"]] = row
    return dataset


def get_replacement_ids() -> list[str]:
    ids = []
    with REPLACEMENT_IDS_FILE.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            ids.append(row["id"])
    return ids


def load_completed() -> set[tuple[str, str, str]]:
    completed = set()
    if RESULTS_OUT.exists():
        with RESULTS_OUT.open("r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                completed.add((row["sample_id"], row["model"], row["strategy"]))
    return completed


def save_checkpoint(completed: int, total: int, errors: int, last_key: str):
    cp = {
        "completed": completed,
        "total": total,
        "errors_remaining": errors,
        "timestamp": datetime.now().isoformat(),
        "last_key": last_key,
    }
    tmp = CHECKPOINT_OUT.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cp, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(CHECKPOINT_OUT)


def process_one(sample_id: str, model: str, strategy: str,
                dataset: dict[str, dict], api: APIClient) -> dict:
    row = dataset.get(sample_id)
    if not row:
        return {
            "sample_id": sample_id, "model": model, "strategy": strategy,
            "true_label": "", "prediction": "", "correct": False,
            "raw_response": "", "error": f"Sample {sample_id} not found"
        }

    try:
        email_content = json.loads(row["email_content"])
    except Exception:
        email_content = {}

    sys_prompt = PromptManager.get_system_prompt(strategy)
    usr_prompt = PromptManager.get_user_prompt(strategy, email_content)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response, error = api.query_model(model, sys_prompt, usr_prompt)
            prediction = Evaluator.parse_response(response)

            if prediction is None and response and not error:
                strict = (
                    f"You previously analyzed an email and responded:\n\n"
                    f'"""{response[:500]}"""\n\n'
                    f"Based on your analysis above, what is your final decision?\n"
                    f"Reply with ONLY the number 0 or 1.\n"
                    f"0 = do not proceed (block)\n"
                    f"1 = proceed (allow)\n\n"
                    f"Your answer (just the digit):"
                )
                r_resp, _ = api.query_model(
                    model, "Reply with ONLY a single digit: 0 or 1. Nothing else.", strict
                )
                retry_pred = Evaluator.parse_response(r_resp)
                if retry_pred is not None:
                    prediction = retry_pred
                    response = f"{response}\n[RETRY]: {r_resp}"
                else:
                    prediction = 0
                    response = f"{response}\n[RETRY_FAILED]: {r_resp}"

            true_label = int(row["phish_label"])
            is_correct = (prediction is not None) and (prediction != true_label)

            if error and error.strip():
                last_error = error
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 + attempt * 3)
                    continue

            return {
                "sample_id": sample_id, "model": model, "strategy": strategy,
                "true_label": true_label,
                "prediction": prediction, "correct": is_correct,
                "raw_response": response, "error": error or ""
            }
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 + attempt * 3)

    return {
        "sample_id": sample_id, "model": model, "strategy": strategy,
        "true_label": "", "prediction": "", "correct": False,
        "raw_response": "", "error": f"Max retries exceeded: {last_error}"
    }


def main():
    print("Task 26 Step 6: Rerun model evaluations for 57 replaced rows")
    print(f"  Started: {datetime.now().isoformat(timespec='seconds')}")

    replacement_ids = get_replacement_ids()
    print(f"  Replacement IDs: {len(replacement_ids)}")

    dataset = load_dataset()
    print(f"  Dataset loaded: {len(dataset)} samples")

    # Build task list
    tasks = []
    for sid in replacement_ids:
        for strategy in ALL_STRATEGIES:
            for model in ALL_MODELS:
                tasks.append((sid, model, strategy))

    total = len(tasks)
    print(f"  Total tasks: {total} ({len(replacement_ids)} x {len(ALL_STRATEGIES)} x {len(ALL_MODELS)})")

    # Check resume
    already_done = load_completed()
    remaining = [(s, m, st) for s, m, st in tasks if (s, m, st) not in already_done]
    print(f"  Already completed: {len(already_done)}")
    print(f"  Remaining: {len(remaining)}")

    if not remaining:
        print("  All tasks already completed.")
        return

    # Init API
    api = APIClient(
        openrouter_key=Config.OPENROUTER_API_KEY,
        google_key=Config.GOOGLE_API_KEY,
        openai_key=Config.OPENAI_API_KEY,
        anthropic_key=Config.ANTHROPIC_API_KEY,
    )

    write_lock = threading.Lock()
    completed_count = len(already_done)
    error_count = 0

    print(f"\n  Starting {len(remaining)} API calls with {MAX_WORKERS} workers...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_one, s, m, st, dataset, api): (s, m, st)
            for s, m, st in remaining
        }

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            completed_count += 1

            with write_lock:
                mode = "a" if RESULTS_OUT.exists() else "w"
                with RESULTS_OUT.open(mode, newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                    if mode == "w":
                        writer.writeheader()
                    writer.writerow({k: result.get(k, "") for k in FIELDNAMES})
                    f.flush()
                    os.fsync(f.fileno())

            if result.get("error", "").strip():
                error_count += 1

            if completed_count % 10 == 0:
                save_checkpoint(completed_count, total, error_count,
                                f"{result['sample_id']}/{result['model']}/{result['strategy']}")

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
                print(f"  Progress: {i+1}/{len(remaining)} "
                      f"({(i+1)/len(remaining)*100:.1f}%) | "
                      f"Errors: {error_count} | "
                      f"ETA: {eta/60:.1f}min", flush=True)

    save_checkpoint(completed_count, total, error_count, "DONE")

    elapsed = time.time() - start_time
    print(f"\n  Completed in {elapsed/60:.1f} minutes")
    print(f"  Total processed: {completed_count}/{total}")
    print(f"  Errors: {error_count}")
    print(f"  Results: {RESULTS_OUT}")

    if error_count > 0:
        print(f"\n  ⚠️  {error_count} errors remain.")
    else:
        print(f"\n  ✅ All evaluations completed successfully!")


if __name__ == "__main__":
    main()
