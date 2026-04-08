# PhishNChips: A Benchmark for LLM Email-Agent Security

PhishNChips is an open-source benchmark for evaluating how system prompt configurations influence the security and false-positive characteristics of LLM-based email agents. This repository contains the reference implementation, evaluation tools, and the canonical v5.2 dataset release.

## Dataset Status: v5.2 (April 2026)

The v5.2 release incorporates the latest repairs and source optimizations:
- **Core Stimuli:** 2,000 professional-grade emails (1,000 phishing / 1,000 legitimate).
- **Reference Grid:** 220,000 evaluations (11 frontier models x 10 prompt strategies).
- **Quality Assured:** Includes a repaired cross-domain legitimate split and verified malicious infrastructure.
- **Ethics & Licensing:** 100% of third-party sources are cleared for academic redistribution.

## Repository Layout

```text
.
├── README.md               # Main overview and quick start
├── SOURCE_LICENSES.md      # Provenance and licensing documentation
├── LICENSE                 # MIT License
├── requirements.txt        # Python dependencies
├── evaluate.py             # Community evaluation tool
├── run_benchmark.py        # Reference benchmark runner
├── prompt_strategies.py    # Definitions of the 10 prompt strategies
├── robust_reparser.py      # LLM response parser
├── BENCHMARK_GUIDE.md      # Implementation and usage tutorial
├── data/                   # Canonical v5.2 data files
│   ├── core_emails.csv
│   ├── benchmark_results.csv
│   ├── reference_results.csv
│   └── croissant.json
└── reproducibility/        # Deterministic generation and audit scripts
```

## Quick Start

### 0. Clone With Git LFS

The dataset CSVs in `data/` are stored via Git LFS. A plain `git clone` will fetch ~132-byte pointer stubs instead of the real files, and the benchmark will not run. Install Git LFS once, then clone (or pull) so the CSVs are materialized:

```bash
git lfs install
git clone https://github.com/R-Lit/PhishNChips.git
# or, if you already cloned without LFS:
cd PhishNChips && git lfs pull
```

You can verify the dataset is materialized by checking that `data/core_emails.csv` is roughly 1.5 MB (not 132 bytes).

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Inspect the v5.2 Dataset
```python
import pandas as pd
core = pd.read_csv("data/core_emails.csv")
print(core["phish_label"].value_counts())
```

### 3. Run an Evaluation
Evaluate your own model or configuration against the benchmark:
```bash
python evaluate.py \
  --model your-model-id \
  --strategy baseline \
  --limit 50
```

## Data Provenance

The benchmark is grounded in real-world threat infrastructure and verified research rankings:

| Source | Role | Status |
|---|---|---|
| **Nazario Corpus** | Validation & Payloads | CC-BY-4.0 |
| **OpenPhish** | Malicious URLs | Academic Approval |
| **PhishTank** | Malicious URLs | Cisco Terms |
| **Tranco** | Benign Domain Seeds | NDSS 2019 Citation |
| **GitHub DB** | Malicious URLs | community-maintained |

Complete details are available in `SOURCE_LICENSES.md`.

## Citation

If you use PhishNChips in your research, please cite:

```bibtex
@article{litvak2026phishnchips,
  title={The System Prompt Is the Attack Surface: How {LLM} Agent Configuration Shapes Security and Creates Exploitable Vulnerabilities},
  author={Litvak, Ron},
  journal={arXiv preprint},
  year={2026}
}
```

## License

Code and synthetic content are released under the **MIT License**. Third-party URL indicators are redistributed under their respective source terms.
