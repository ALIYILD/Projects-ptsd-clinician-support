# Architecture

## MVP Stack

- SQLite for local evidence storage
- Python ingestion pipeline for literature and later guideline sources
- retrieval layer for citation-backed search
- safety rules configuration separate from model logic
- WSGI JSON backend for UI integration

## Data Layers

1. Raw literature exports in `source_files`
2. Canonical article layer in `articles`
3. Provenance-preserving source rows in `article_sources`
4. Structured guideline and recommendation layer
5. Retrieval and clinician-support service layer

## Current Storage Model

- `articles`: canonical deduplicated records
- `article_sources`: one row per upstream record
- `article_authors`: parsed author list
- `article_publication_types`: normalized publication types from PubMed-like files
- `article_condition_tags`: condition linkage, seeded with PTSD
- `guidelines` and `guideline_recommendations`: first-class guideline storage

## Next Additions

- study-type classification
- intervention and outcome extraction
- guideline parser/importer
- patient-case model
- explainable recommendation engine
- local web or TUI review interface
