# PhishNChips Release Rules

These rules describe the Task 26 candidate release. They supersede older v4 notes that mentioned `phish_run`, `urlhaus`, or a 9-strategy benchmark.

## Dataset Rules

- The core benchmark must remain balanced: 1,000 phishing and 1,000 legitimate examples.
- Core rows must have stable `id` values.
- `email_content` must remain valid JSON.
- `url_raw` must match the URL represented inside `email_content` unless a future manifest explicitly documents a schema change.
- `phish_label = 1` means the link should be blocked; `phish_label = 0` means the link should be allowed.
- `phish_run` and `urlhaus` must remain absent from the Task 26 candidate core dataset unless a new source-permission task explicitly reintroduces them.

## Legitimate Cross-Domain Rules

- `cross_domain_expansion_v1` examples must remain legitimate.
- They should use real provider-owned public URLs, not invented private document IDs, meeting IDs, invoice IDs, ticket IDs, or tenant subdomains.
- Fictional sender organizations are allowed, but the provider URL and the email prose must match.
- The examples must remain non-trivial: do not make every sender domain match every URL domain, and do not add text such as "this is safe" or "not phishing" to force model behavior.

## Phishing URL Rules

- Phishing URL indicators must come from cleared or documented sources.
- Do not relabel benign URLs as phishing.
- Do not download malware, retrieve payloads, or require users to visit malicious URLs.
- Use offline URL strings and synthetic email contexts for defensive benchmarking.
- Keep source provenance in `SOURCE_LICENSES.md` and in the relevant audit manifest.

## Evaluation Rules

- The canonical Task 26 grid is 2,000 samples x 10 strategies x 11 models = 220,000 result rows.
- Every `(sample_id, strategy, model)` pair must be unique.
- Non-empty `error` rows must be resolved or explicitly documented before results are treated as canonical.
- Use temperature `0.0` for comparability with the reference grid.
- Report recall and false-positive rate together. A model that blocks everything is not a deployable system.
- Safetility is a summary score, not a replacement for reading recall, FPR, infrastructure recall, and cross-domain FPR.

## Source-License Rules

- Do not mark the NeurIPS existing-assets checklist item complete until every source in `SOURCE_LICENSES.md` has a final release decision.
- Do not claim the entire dataset is MIT. Code may be MIT; third-party-derived URL indicators and source-derived auxiliary rows retain their source-specific terms.
- Preserve the OpenPhish approval proof in the private audit trail and cite the approval status in the source notice.

