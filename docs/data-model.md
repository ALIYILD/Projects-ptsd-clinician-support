# Data Model

## Principles

- Keep canonical records separate from source rows.
- Preserve raw source payloads for traceability.
- Use DOI first, then PMID, then source-native ID for canonical identity.
- Treat exported subset files as derived convenience inputs, not primary truth.

## Main Tables

- `conditions`
- `sources`
- `source_files`
- `ingest_runs`
- `articles`
- `article_sources`
- `article_authors`
- `article_publication_types`
- `article_condition_tags`
- `guidelines`
- `guideline_recommendations`
- `guideline_article_links`

## Dedupe Strategy

1. normalized DOI
2. PMID
3. source name + native source ID
4. normalized title review step only if needed later

## MVP Query Shapes

- latest PTSD articles
- review or clinical-trial subsets
- guideline-backed articles
- source provenance for a cited article
