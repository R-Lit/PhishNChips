#!/usr/bin/env python3
"""Task 26: Replace phish_run (40) + urlhaus (17) rows with real PhishTank/OpenPhish URLs.

Steps 1-5: Extract targets, source replacement URLs, build replacement rows,
validate, and build repaired dataset candidate.

Safety: URLs are text indicators only — never visited/detonated.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

NEURIPS = Path(__file__).resolve().parent.parent
DATASET = NEURIPS / "dataset_v5" / "phishnchips_v5_qa_repaired_dataset.csv"

# Outputs
TARGET_CSV = NEURIPS / "dataset_v5" / "v5.2_replacement_targets.csv"
TARGET_AUDIT = NEURIPS / "audit" / "v5.2_replacement_target_audit.md"
CANDIDATE_URLS_CSV = NEURIPS / "dataset_v5" / "v5.2_candidate_replacement_urls.csv"
REPLACEMENT_ROWS_CSV = NEURIPS / "dataset_v5" / "v5.2_replacement_rows_candidate.csv"
REPAIRED_DATASET = NEURIPS / "dataset_v5" / "phishnchips_v5_v5.2_repaired_dataset.csv"
STATIC_VALIDATION = NEURIPS / "audit" / "v5.2_static_validation.md"
REPLACEMENT_PLAN = NEURIPS / "audit" / "v5.2_replacement_plan.md"

DATASET_FIELDS = ["id", "url_raw", "phish_label", "email_content", "strategy", "url_category", "datasource", "model_used"]
SEED = 2026

# ── Phishing URL harvesting (text-only, no visits) ─────────────────────────

def fetch_openphish_urls() -> list[dict]:
    """Fetch OpenPhish community feed URLs as text indicators."""
    import urllib.request
    try:
        req = urllib.request.Request("https://openphish.com/feed.txt",
                                    headers={"User-Agent": "phishnchips-academic-benchmark/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            urls = resp.read().decode("utf-8", errors="replace").strip().split("\n")
        return [{"url": u.strip(), "source": "openphish",
                 "source_record_id": f"openphish_feed_{i}",
                 "feed_name": "openphish_community_feed",
                 "access_date": datetime.now().strftime("%Y-%m-%d")}
                for i, u in enumerate(urls) if u.strip().startswith("http")]
    except Exception as e:
        print(f"  Warning: OpenPhish fetch failed: {e}")
        return []

def fetch_phishtank_urls(limit: int = 500) -> list[dict]:
    """Fetch PhishTank verified URLs as text indicators."""
    import urllib.request
    try:
        req = urllib.request.Request("http://data.phishtank.com/data/online-valid.csv",
                                   headers={"User-Agent": "phishtank/phishnchips_academic"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        reader = csv.DictReader(content.strip().split("\n"))
        results = []
        for i, row in enumerate(reader):
            if i >= limit:
                break
            results.append({
                "url": row.get("url", "").strip(),
                "source": "phishtank",
                "source_record_id": f"phishtank_{row.get('phish_id', i)}",
                "feed_name": "phishtank_online_valid",
                "access_date": datetime.now().strftime("%Y-%m-%d"),
                "target": row.get("target", ""),
            })
        return results
    except Exception as e:
        print(f"  Warning: PhishTank fetch failed: {e}")
        return []

# ── URL classification helpers ──────────────────────────────────────────────

def classify_url(url: str) -> str:
    """Assign a url_category based on the URL pattern."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if "github.io" in host or "github.com" in host:
        return "github_pages"
    if "forms.gle" in host or "docs.google.com" in host or "drive.google.com" in host:
        return "google_docs"
    if "firebase" in host or "firebasestorage" in host or ".web.app" in host:
        return "firebase"
    if "ipfs.io" in host or "ipfs" in host:
        return "ipfs"
    if any(s in host for s in ["bit.ly", "tinyurl.com", "t.co", "is.gd", "ow.ly", "cutt.ly", "rebrand.ly", "shorturl"]):
        return "url_shortener"
    if "netlify" in host or "vercel" in host or "herokuapp" in host or "glitch" in host:
        return "hosting_platform"
    if "onedrive" in host or "sharepoint" in host or "1drv.ms" in host:
        return "microsoft_cloud"
    if "dropbox" in host:
        return "cloud_storage"
    if any(s in host for s in [".shop", ".xyz", ".top", ".buzz", ".icu", ".club", ".online"]):
        return "suspicious_tld"
    if re.match(r"^\d+\.\d+\.\d+\.\d+", host):
        return "direct_ip"
    if len(host) > 30 or host.count(".") >= 4:
        return "long_domain"
    return "other_https"

# ── Email body generation ───────────────────────────────────────────────────

CORPORATE_DOMAINS = [
    "nexgenpartners.com", "silverlinecorp.com", "meridianinc.com", "brightpathco.com",
    "pinnacletech.co", "redwoodanalytics.com", "atlasconsulting.com", "catalystcorp.com",
    "solidrockgroup.com", "ridgelinetech.com", "blueskyventures.com", "acmecorp.com",
    "technovagroup.com", "novawavetech.com", "blueprintworks.co", "titaniumsystems.com",
    "harborviewcorp.com", "compasspointinc.com", "summitworks.io", "evergreenpartners.com",
]

FIRST_NAMES = [
    "Maya", "Ethan", "Priya", "Noah", "Olivia", "Leo", "Sofia", "Adrian", "Hannah", "Victor",
    "Alicia", "Marcus", "Elena", "Jonah", "Nina", "Caleb", "Isabel", "Owen", "Tara", "Julian",
    "Lisa", "Kevin", "Emily", "Andrew", "Sarah", "David", "Rachel", "Brian", "Michelle", "Steven",
]
LAST_NAMES = [
    "Bennett", "Shah", "Morrison", "Ng", "Alvarez", "Hughes", "Fischer", "Raman", "Sullivan",
    "Park", "Kim", "Dawson", "Patel", "Reyes", "Murphy", "Garcia", "Coleman", "Brooks", "Torres",
    "Singh", "Chen", "Rodriguez", "Lee", "Foster", "Williams",
]
RECIPIENTS = ["Avery", "Jordan", "Taylor", "Morgan", "Riley", "Sam", "Casey", "Jamie", "Quinn", "Parker"]
ROLES = [
    "Product Manager", "Engineering Lead", "Operations Director", "Program Manager",
    "IT Administrator", "Marketing Lead", "Senior Analyst", "Team Lead", "Account Manager",
]

# Phishing email templates — calm, plausible workplace messages that hide the malicious URL
PHISHING_TEMPLATES = [
    {
        "subject": "Updated project documentation — please review",
        "body": "Hi {recipient},\n\nI've uploaded the latest version of the project documentation per our discussion last week. The file includes the revised milestones and updated resource allocation table.\n\nPlease review when you get a chance and let me know if anything needs adjusting before the Friday call.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["View document", "Open documentation", "Review file"],
    },
    {
        "subject": "Shared notes from yesterday's planning session",
        "body": "Hello {recipient},\n\nAttaching the notes from the planning session we had yesterday afternoon. I captured the key decisions and open items so everyone is on the same page.\n\nFeel free to add any corrections.\n\n{link_text}\n\nRegards,\n{sender}\n{role}, {company}",
        "link_texts": ["View notes", "Open meeting notes", "Access shared file"],
    },
    {
        "subject": "Code review ready — feature branch changes",
        "body": "Hi {recipient},\n\nThe feature branch changes are ready for your review. I addressed the feedback from last sprint and added the integration tests we discussed.\n\nWould appreciate your input before we merge.\n\n{link_text}\n\nThanks,\n{sender}\n{role}, {company}",
        "link_texts": ["View pull request", "Open code review", "Review changes"],
    },
    {
        "subject": "Vendor proposal — attached for your review",
        "body": "Hi {recipient},\n\nThe vendor sent over their proposal for the upcoming engagement. I've uploaded it to the shared workspace so the team can review it together.\n\nLet me know your thoughts when you have a few minutes.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["View proposal", "Open vendor document", "Review proposal"],
    },
    {
        "subject": "Onboarding resources for new team members",
        "body": "Hello {recipient},\n\nI put together a set of onboarding resources for the new hires joining next week. The folder includes the team handbook, access request forms, and a quick-start guide.\n\nPlease share this with anyone who needs it.\n\n{link_text}\n\nRegards,\n{sender}\n{role}, {company}",
        "link_texts": ["Open onboarding folder", "Access resources", "View materials"],
    },
    {
        "subject": "Design mockups — latest iteration",
        "body": "Hi {recipient},\n\nThe design team finished the latest round of mockups for the dashboard redesign. I uploaded the files so you can preview them before the stakeholder review.\n\nWould love your feedback.\n\n{link_text}\n\nThanks,\n{sender}\n{role}, {company}",
        "link_texts": ["View mockups", "Open design files", "Preview designs"],
    },
    {
        "subject": "Budget spreadsheet — Q3 actuals",
        "body": "Hello {recipient},\n\nThe Q3 actuals are ready. I consolidated the numbers from all departments and highlighted the variances we should discuss at the review meeting.\n\nPlease take a look when convenient.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["Open spreadsheet", "View budget file", "Review Q3 numbers"],
    },
    {
        "subject": "Training materials — compliance module",
        "body": "Hi {recipient},\n\nThe updated compliance training materials are now available. The module covers the latest policy changes and includes a short knowledge check at the end.\n\nPlease complete it before the end of the month.\n\n{link_text}\n\nRegards,\n{sender}\n{role}, {company}",
        "link_texts": ["Start training", "Open module", "Access training"],
    },
    {
        "subject": "Client presentation — final draft",
        "body": "Hi {recipient},\n\nAttaching the final draft of the client presentation for your sign-off. I incorporated the edits from the last review and updated the competitive analysis section.\n\nLet me know if it's good to share.\n\n{link_text}\n\nThanks,\n{sender}\n{role}, {company}",
        "link_texts": ["View presentation", "Open slides", "Review final draft"],
    },
    {
        "subject": "Quick survey — team feedback on process changes",
        "body": "Hello {recipient},\n\nWe're gathering feedback on the recent process changes. The survey is short, about 3 minutes, and your input will help shape the next iteration.\n\nWould really appreciate your response.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["Take survey", "Open survey", "Share feedback"],
    },
    {
        "subject": "Shared resource — internal wiki update",
        "body": "Hi {recipient},\n\nI updated the internal wiki with the latest architectural decisions and deployment notes. The changes should help the team during the migration next quarter.\n\nFeel free to edit or add comments.\n\n{link_text}\n\nRegards,\n{sender}\n{role}, {company}",
        "link_texts": ["Open wiki", "View updates", "Access wiki page"],
    },
    {
        "subject": "Contract draft — partnership terms",
        "body": "Hello {recipient},\n\nThe legal team finalized the draft partnership terms. I uploaded the document so both sides can review the marked sections before the call.\n\nPlease review the highlighted clauses.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["View contract", "Open draft", "Review terms"],
    },
    {
        "subject": "Analysis report — market research findings",
        "body": "Hi {recipient},\n\nHere's the market research report we discussed. It covers the competitive landscape, pricing benchmarks, and a few recommendations for the product team.\n\nWorth a read before the strategy meeting.\n\n{link_text}\n\nThanks,\n{sender}\n{role}, {company}",
        "link_texts": ["Read report", "Open analysis", "View findings"],
    },
    {
        "subject": "Invitation — team offsite planning doc",
        "body": "Hi {recipient},\n\nThe planning document for the upcoming offsite is ready. It includes the agenda, logistics, and a short section for session preferences.\n\nPlease add your input by Thursday.\n\n{link_text}\n\nRegards,\n{sender}\n{role}, {company}",
        "link_texts": ["Open planning doc", "View agenda", "Add your input"],
    },
    {
        "subject": "Release notes — v4.2 deployment",
        "body": "Hello {recipient},\n\nThe release notes for the v4.2 deployment are posted. This release includes the performance fixes, the new notification system, and several minor UI improvements.\n\nPlease review before the rollout.\n\n{link_text}\n\nBest,\n{sender}\n{role}, {company}",
        "link_texts": ["View release notes", "Open changelog", "Review deployment"],
    },
]


def build_replacement_rows(
    target_ids: list[str],
    candidate_urls: list[dict],
    existing_urls: set[str],
    rng: random.Random,
) -> list[dict]:
    """Build 57 replacement rows with real phishing URLs and synthetic email bodies."""

    # Filter candidates: no duplicates, not already in dataset
    used_urls = set()
    filtered = []
    for c in candidate_urls:
        url = c["url"]
        if url not in existing_urls and url not in used_urls:
            used_urls.add(url)
            filtered.append(c)

    if len(filtered) < len(target_ids):
        raise ValueError(f"Not enough candidate URLs: need {len(target_ids)}, got {len(filtered)}")

    # Select URLs — prefer diverse categories
    selected = filtered[:len(target_ids)]

    rows = []
    used_subjects = set()

    for i, row_id in enumerate(target_ids):
        url_info = selected[i]
        url = url_info["url"]
        source = url_info["source"]
        category = classify_url(url)

        template = PHISHING_TEMPLATES[i % len(PHISHING_TEMPLATES)]
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        sender_name = f"{first} {last}"
        recipient = rng.choice(RECIPIENTS)
        role = rng.choice(ROLES)
        corp_domain = CORPORATE_DOMAINS[i % len(CORPORATE_DOMAINS)]
        company = corp_domain.split(".")[0].replace("-", " ").title()
        from_addr = f"{first.lower()}.{last.lower()}@{corp_domain}"
        link_text = rng.choice(template["link_texts"])

        subject = template["subject"]
        # Ensure unique subjects
        attempt = 0
        while subject in used_subjects and attempt < 20:
            alt_template = rng.choice(PHISHING_TEMPLATES)
            subject = alt_template["subject"]
            template = alt_template
            attempt += 1
        used_subjects.add(subject)

        body = template["body"].format(
            recipient=recipient,
            sender=sender_name,
            role=role,
            company=company,
            link_text=link_text,
        )

        email_content = {
            "sender": sender_name,
            "from": from_addr,
            "subject": subject,
            "body": body,
            "link_display_text": link_text,
            "link_url": url,
        }

        rows.append({
            "id": row_id,
            "url_raw": url,
            "phish_label": 1,
            "email_content": json.dumps(email_content, ensure_ascii=True),
            "strategy": category,
            "url_category": category,
            "datasource": source,
            "model_used": "v5.2_replacement_v1",
        })

    return rows


def validate_replacements(rows: list[dict], existing_urls: set[str], target_ids: list[str]) -> list[str]:
    """Run static validation. Returns list of errors."""
    errors = []

    if len(rows) != 57:
        errors.append(f"Expected 57 rows, got {len(rows)}")

    ids = [r["id"] for r in rows]
    if sorted(ids) != sorted(target_ids):
        errors.append(f"IDs don't match target IDs")

    if len(set(ids)) != len(ids):
        errors.append(f"Duplicate IDs found")

    urls = [r["url_raw"] for r in rows]
    if len(set(urls)) != len(urls):
        errors.append(f"Duplicate URLs found")

    bodies = []
    for row in rows:
        assert row["phish_label"] == 1 or row["phish_label"] == "1", f"{row['id']} wrong label"

        ec = json.loads(row["email_content"])
        required = {"sender", "from", "subject", "body", "link_display_text", "link_url"}
        missing = required - set(ec.keys())
        if missing:
            errors.append(f"{row['id']} missing email fields: {missing}")

        if ec["link_url"] != row["url_raw"]:
            errors.append(f"{row['id']} link_url != url_raw")

        bodies.append(ec["body"])

        # Check for placeholder strings
        for banned in ["fill", "example.com", "TODO", "placeholder"]:
            if banned in row["url_raw"].lower():
                errors.append(f"{row['id']} URL contains banned string: {banned}")

        if row["url_raw"] in existing_urls:
            errors.append(f"{row['id']} URL already exists in dataset: {row['url_raw'][:60]}")

        if row["datasource"] not in ("phishtank", "openphish"):
            errors.append(f"{row['id']} invalid datasource: {row['datasource']}")

    if len(set(bodies)) != len(bodies):
        errors.append(f"Duplicate email bodies found")

    return errors


def main():
    print("Task 26: Replace phish_run + urlhaus rows")
    print(f"  Started: {datetime.now().isoformat(timespec='seconds')}")
    rng = random.Random(SEED)

    # Step 1: Extract target rows
    print("\n=== Step 1: Extract target rows ===")
    all_rows = []
    existing_urls = set()
    target_rows = []
    with DATASET.open("r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            all_rows.append(row)
            existing_urls.add(row["url_raw"])
            if row["datasource"] in ("phish_run", "urlhaus"):
                target_rows.append(row)

    target_ids = [r["id"] for r in target_rows]
    print(f"  Total dataset rows: {len(all_rows)}")
    print(f"  Target rows: {len(target_rows)} ({sum(1 for r in target_rows if r['datasource']=='phish_run')} phish_run + {sum(1 for r in target_rows if r['datasource']=='urlhaus')} urlhaus)")

    # Remove target URLs from existing set (they'll be replaced)
    for r in target_rows:
        existing_urls.discard(r["url_raw"])

    # Write target CSV
    TARGET_CSV.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        writer.writerows(target_rows)
    print(f"  Wrote: {TARGET_CSV}")

    # Write target audit
    TARGET_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_AUDIT.open("w", encoding="utf-8") as f:
        f.write("# Task 26 Replacement Target Audit\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"Total targets: {len(target_rows)} (40 phish_run + 17 urlhaus)\n\n")
        f.write("## Target Rows\n\n")
        f.write("| ID | Datasource | URL Category | URL (truncated) | Subject |\n")
        f.write("|---|---|---|---|---|\n")
        for r in target_rows:
            ec = json.loads(r["email_content"])
            f.write(f"| `{r['id']}` | {r['datasource']} | {r.get('url_category','')} | `{r['url_raw'][:50]}` | {ec.get('subject','')[:40]} |\n")
    print(f"  Wrote: {TARGET_AUDIT}")

    # Step 2: Source replacement URLs
    print("\n=== Step 2: Source replacement URLs ===")
    openphish_urls = fetch_openphish_urls()
    phishtank_urls = fetch_phishtank_urls(limit=500)
    print(f"  OpenPhish URLs fetched: {len(openphish_urls)}")
    print(f"  PhishTank URLs fetched: {len(phishtank_urls)}")

    # Prioritize diversity: mix sources
    # Prefer URLs that match interesting categories (github, google, firebase, etc.)
    interesting_hosts = ["github", "google", "firebase", "ipfs", "onedrive", "sharepoint",
                         "dropbox", "netlify", "vercel", "web.app", "forms", "drive",
                         "bit.ly", "tinyurl", "t.co"]

    def score_url(u):
        host = urlparse(u["url"]).netloc.lower()
        for h in interesting_hosts:
            if h in host:
                return 2
        return 1

    all_candidates = openphish_urls + phishtank_urls
    # Filter out invalid URLs and existing ones
    all_candidates = [c for c in all_candidates
                      if c["url"].startswith("http") and c["url"] not in existing_urls]

    # Sort by interest score descending, then shuffle within tiers
    all_candidates.sort(key=lambda x: -score_url(x))
    # Take diverse selection
    rng.shuffle(all_candidates[0:100])  # Shuffle interesting ones
    rng.shuffle(all_candidates[100:])    # Shuffle rest

    # Write candidate URLs CSV
    with CANDIDATE_URLS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_url", "source", "source_record_id_or_feed_date",
                         "source_url_or_feed_name", "access_date", "source_category_hint", "notes"])
        for c in all_candidates[:100]:
            cat = classify_url(c["url"])
            writer.writerow([c["url"], c["source"], c.get("source_record_id", ""),
                            c.get("feed_name", ""), c["access_date"], cat, ""])
    print(f"  Wrote {min(100, len(all_candidates))} candidates: {CANDIDATE_URLS_CSV}")

    # Step 3: Build replacement rows
    print("\n=== Step 3: Build replacement rows ===")
    replacement_rows = build_replacement_rows(target_ids, all_candidates, existing_urls, rng)
    print(f"  Built {len(replacement_rows)} replacement rows")

    # Write replacement rows
    with REPLACEMENT_ROWS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        writer.writerows(replacement_rows)
    print(f"  Wrote: {REPLACEMENT_ROWS_CSV}")

    # Step 4: Static validation
    print("\n=== Step 4: Static validation ===")
    validation_errors = validate_replacements(replacement_rows, existing_urls, target_ids)

    with STATIC_VALIDATION.open("w", encoding="utf-8") as f:
        f.write("# Task 26 Static Validation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"Rows: {len(replacement_rows)}\n")
        f.write(f"Unique IDs: {len(set(r['id'] for r in replacement_rows))}\n")
        f.write(f"Unique URLs: {len(set(r['url_raw'] for r in replacement_rows))}\n")

        source_counts = Counter(r["datasource"] for r in replacement_rows)
        f.write(f"\nSource distribution: {dict(source_counts)}\n")

        cat_counts = Counter(r["url_category"] for r in replacement_rows)
        f.write(f"\nCategory distribution:\n")
        for c, n in cat_counts.most_common():
            f.write(f"  {c}: {n}\n")

        if validation_errors:
            f.write(f"\n## ERRORS ({len(validation_errors)})\n\n")
            for e in validation_errors:
                f.write(f"- {e}\n")
        else:
            f.write(f"\n## ✅ All validations passed\n")
    print(f"  Wrote: {STATIC_VALIDATION}")

    if validation_errors:
        print(f"  ❌ {len(validation_errors)} validation errors:")
        for e in validation_errors:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print(f"  ✅ All validations passed")

    # Step 5: Build repaired dataset candidate
    print("\n=== Step 5: Build repaired dataset candidate ===")
    replacement_map = {r["id"]: r for r in replacement_rows}
    repaired = []
    replaced_count = 0
    for row in all_rows:
        if row["id"] in replacement_map:
            repaired.append(replacement_map[row["id"]])
            replaced_count += 1
        else:
            repaired.append(row)

    with REPAIRED_DATASET.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        writer.writerows(repaired)

    # Verify counts
    new_source_counts = Counter(r["datasource"] for r in repaired)
    print(f"  Total rows: {len(repaired)}")
    print(f"  Replaced: {replaced_count}")
    print(f"  phish_run remaining: {new_source_counts.get('phish_run', 0)}")
    print(f"  urlhaus remaining: {new_source_counts.get('urlhaus', 0)}")
    print(f"  New source counts:")
    for s, c in new_source_counts.most_common():
        print(f"    {s}: {c}")
    print(f"  Wrote: {REPAIRED_DATASET}")

    # Write replacement plan
    with REPLACEMENT_PLAN.open("w", encoding="utf-8") as f:
        f.write("# Task 26 Replacement Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"Replaced {replaced_count} rows (40 phish_run + 17 urlhaus) with real PhishTank/OpenPhish URLs.\n\n")
        f.write("## Per-Row Rationale\n\n")
        for r in replacement_rows:
            ec = json.loads(r["email_content"])
            f.write(f"- **{r['id']}**: Replaced with `{r['datasource']}` URL (`{r['url_category']}` category). ")
            f.write(f"Subject: \"{ec['subject'][:50]}\". URL: `{r['url_raw'][:60]}`\n")
    print(f"  Wrote: {REPLACEMENT_PLAN}")

    print(f"\n✅ Steps 1-5 complete. Ready for Step 6 (model evaluations).")


if __name__ == "__main__":
    main()
