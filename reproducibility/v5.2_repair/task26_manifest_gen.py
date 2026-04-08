#!/usr/bin/env python3
"""Task 26 Step 9: Create Manifest."""

import hashlib
from datetime import datetime
from pathlib import Path

NEURIPS = Path(__file__).resolve().parent.parent

# Files to hash
FILES_TO_HASH = {
    "Target List": "dataset_v5/v5.2_replacement_targets.csv",
    "Candidate URLs": "dataset_v5/v5.2_candidate_replacement_urls.csv",
    "Replacement Rows": "dataset_v5/v5.2_replacement_rows_candidate.csv",
    "Dataset Candidate": "dataset_v5/phishnchips_v5_v5.2_repaired_dataset.csv",
    "Results Supplement": "dataset_v5/v5.2_replacement_results.csv",
    "Merged Results": "dataset_v5/benchmark_results_v5_v5.2_repaired.csv",
    "Scripts (Build)": "dataset_v5/v5.2_build_replacements.py",
    "Scripts (Eval)": "dataset_v5/v5.2_eval_runner.py",
    "Scripts (Merge)": "dataset_v5/v5.2_merge_results.py",
}

def get_hash(rel_path):
    p = NEURIPS / rel_path
    if p.exists():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    return "MISSING"

def main():
    print("Task 26 Step 9: Manifest Generation")
    
    out_path = NEURIPS / "audit" / "v5.2_replacement_manifest.md"
    
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Task 26: Replacement of `phish_run` and `urlhaus` Manifest\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        
        f.write("## Overview\n")
        f.write("Task 26 replaces 57 phishing rows with unknown or uncleared provenance (40 `phish_run`, 17 `urlhaus`) ")
        f.write("with real verfied phishing URLs pulled from PhishTank and OpenPhish alongside synthetic, ")
        f.write("benign-looking, plausible workplace email contexts. No URLs were visited directly (used as text indicators). ")
        f.write("This directly clears the path for the `SOURCE_LICENSES.md` documentation by eliminating those unresolvable dependencies.\n\n")
        
        f.write("## File Checksums\n\n")
        f.write("| Component | File Path | SHA-256 |\n")
        f.write("|---|---|---|\n")
        for friendly, rel in FILES_TO_HASH.items():
            f.write(f"| {friendly} | `{rel}` | `{get_hash(rel)}` |\n")
            
        f.write("\n## Execution Details\n\n")
        f.write("1. **Replacement Source Proofs**: Random selections sampled heavily from the OpenPhish and PhishTank datastreams via script on 2026-04-07. Detailed source records per URL available in `v5.2_candidate_replacement_urls.csv`.\n")
        f.write("2. **Model Evaluation Detail**: The identical 11 OpenRouter (and direct) model panel and 10 parsed strategy techniques were utilized via `v5.2_eval_runner.py`. The generation used `temperature=0.0` to preserve the original deterministic behavior of the models.\n")
        f.write("3. **Source License Implications (Task 22)**: OpenPhish rows increased by 50, PhishTank rows increased by 7. `urlhaus` and `phish_run` counts are reduced to 0 in the `_v5.2_repaired` candidate set. These datasets have required OpenPhish/PhishTank attributions that will be formalized in Task 22.\n")
        f.write("4. **Canonical Files**: No canonical submission, Hugging Face, or standard tracking files were altered directly. The promotion relies on manual validation to convert `dataset_v5/phishnchips_v5_v5.2_repaired_dataset.csv` into `dataset_v5/phishnchips_v5_dataset.csv`.\n")
        
    print(f"  Wrote: {out_path}")

if __name__ == "__main__":
    main()
