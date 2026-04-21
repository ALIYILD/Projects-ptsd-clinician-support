# Treatment Rules

Deterministic treatment-support rules are stored in:

- `config/treatment_rules.json`

Domains covered:

- psychotherapy
- medication
- neuromodulation
- supplements

Each domain defines:

- hard blockers from red flags
- blocker categories from contraindications
- linked guideline domains
- review-only domain messaging

The rules engine does not prescribe or order treatment. It only marks:

- `review`
- `blocked`
- `unsupported`
