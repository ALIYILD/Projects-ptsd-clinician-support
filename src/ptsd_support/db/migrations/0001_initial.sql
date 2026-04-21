CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    icd10_code TEXT,
    dsm5_code TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    format TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parser_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    source_name TEXT NOT NULL,
    input_path TEXT NOT NULL,
    source_file_id INTEGER REFERENCES source_files(id) ON DELETE SET NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    canonical_key TEXT NOT NULL UNIQUE,
    pmid TEXT,
    doi TEXT,
    title TEXT NOT NULL,
    abstract_text TEXT,
    authors TEXT,
    journal TEXT,
    publication_year INTEGER,
    publication_date TEXT,
    is_open_access INTEGER,
    has_fulltext_link INTEGER,
    record_status TEXT NOT NULL DEFAULT 'active',
    normalized_title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_pmid_unique
ON articles(pmid)
WHERE pmid IS NOT NULL AND pmid <> '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_doi_unique
ON articles(doi)
WHERE doi IS NOT NULL AND doi <> '';

CREATE INDEX IF NOT EXISTS idx_articles_publication_year
ON articles(publication_year);

CREATE INDEX IF NOT EXISTS idx_articles_record_status_year
ON articles(record_status, publication_year DESC);

CREATE INDEX IF NOT EXISTS idx_articles_normalized_title
ON articles(normalized_title);

CREATE TABLE IF NOT EXISTS article_sources (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_native_id TEXT NOT NULL,
    source_subtype TEXT,
    source_file_id INTEGER REFERENCES source_files(id) ON DELETE SET NULL,
    source_url TEXT,
    raw_row_json TEXT NOT NULL,
    cited_by_count INTEGER,
    in_epmc INTEGER,
    in_pmc INTEGER,
    is_open_access INTEGER,
    has_pdf INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_article_sources_unique
ON article_sources(source_name, source_native_id, source_file_id);

CREATE INDEX IF NOT EXISTS idx_article_sources_article
ON article_sources(article_id);

CREATE TABLE IF NOT EXISTS article_authors (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    author_ordinal INTEGER NOT NULL,
    display_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_article_authors_article
ON article_authors(article_id, author_ordinal);

CREATE TABLE IF NOT EXISTS article_publication_types (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    publication_type TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_article_publication_types_lookup
ON article_publication_types(publication_type, article_id);

CREATE TABLE IF NOT EXISTS article_condition_tags (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    condition_id INTEGER NOT NULL REFERENCES conditions(id) ON DELETE CASCADE,
    tag_source TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_article_condition_tags_unique
ON article_condition_tags(article_id, condition_id, tag_source);

CREATE TABLE IF NOT EXISTS guidelines (
    id INTEGER PRIMARY KEY,
    condition_id INTEGER REFERENCES conditions(id) ON DELETE SET NULL,
    guideline_key TEXT,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    version_label TEXT,
    publication_date TEXT,
    review_date TEXT,
    source_url TEXT NOT NULL,
    jurisdiction TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    source_file_path TEXT,
    summary TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_guidelines_key_unique
ON guidelines(guideline_key)
WHERE guideline_key IS NOT NULL AND guideline_key <> '';

CREATE TABLE IF NOT EXISTS guideline_recommendations (
    id INTEGER PRIMARY KEY,
    guideline_id INTEGER NOT NULL REFERENCES guidelines(id) ON DELETE CASCADE,
    recommendation_key TEXT,
    clinical_domain TEXT NOT NULL,
    population TEXT,
    recommendation_text TEXT NOT NULL,
    modality TEXT,
    strength TEXT,
    evidence_basis TEXT,
    notes_json TEXT,
    caution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_guideline_recommendations_domain
ON guideline_recommendations(clinical_domain);

CREATE INDEX IF NOT EXISTS idx_guideline_recommendations_topic_modality
ON guideline_recommendations(clinical_domain, modality);

CREATE TABLE IF NOT EXISTS guideline_article_links (
    id INTEGER PRIMARY KEY,
    guideline_recommendation_id INTEGER NOT NULL REFERENCES guideline_recommendations(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL,
    match_method TEXT,
    confidence REAL
);

CREATE INDEX IF NOT EXISTS idx_guideline_article_links_lookup
ON guideline_article_links(article_id, guideline_recommendation_id);

CREATE TABLE IF NOT EXISTS patient_cases (
    id INTEGER PRIMARY KEY,
    case_key TEXT NOT NULL UNIQUE,
    patient_id TEXT NOT NULL,
    clinician_id TEXT,
    age INTEGER,
    trauma_exposure_summary TEXT,
    symptom_duration_weeks INTEGER,
    functional_impairment TEXT,
    symptoms_json TEXT NOT NULL DEFAULT '[]',
    comorbidities_json TEXT NOT NULL DEFAULT '[]',
    medications_json TEXT NOT NULL DEFAULT '[]',
    flags_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_cases_patient
ON patient_cases(patient_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS case_reviews (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES patient_cases(id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    review_type TEXT NOT NULL,
    review_status TEXT NOT NULL,
    note TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_case_reviews_case
ON case_reviews(case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS case_recommendation_history (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES patient_cases(id) ON DELETE CASCADE,
    recommendation_domain TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_case_recommendation_history_case
ON case_recommendation_history(case_id, created_at DESC);
