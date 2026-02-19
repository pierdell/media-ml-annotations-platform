-- Index Factory – Bootstrap Schema
-- This runs once when the postgres container is first created.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- trigram index for fuzzy text search

-- ── Users ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    username    VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── Objects (e.g. "trees") ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS objects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_objects_user ON objects(user_id);

-- ── Ontology nodes (hierarchical properties) ─────────────────────
CREATE TABLE IF NOT EXISTS ontology_nodes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    object_id   UUID NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES ontology_nodes(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    color       VARCHAR(7),          -- hex colour for UI badges
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ontology_object ON ontology_nodes(object_id);
CREATE INDEX idx_ontology_parent ON ontology_nodes(parent_id);

-- ── Reference media (images, videos, etc.) ───────────────────────
CREATE TABLE IF NOT EXISTS reference_media (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    object_id     UUID NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    file_path     TEXT NOT NULL,
    file_name     VARCHAR(512) NOT NULL,
    mime_type     VARCHAR(127),
    file_size     BIGINT,
    thumbnail_path TEXT,
    metadata      JSONB DEFAULT '{}',
    indexed       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_refmedia_object ON reference_media(object_id);

-- ── Ingested documents (web pages, markdown, pdf …) ──────────────
CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type   VARCHAR(50) NOT NULL,   -- 'webpage', 'markdown', 'pdf', 'text'
    source_url    TEXT,
    title         VARCHAR(512),
    raw_text      TEXT,
    metadata      JSONB DEFAULT '{}',
    indexed       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_source ON documents(source_type);

-- ── Document chunks (for embedding) ──────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    token_count   INTEGER,
    indexed       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);

-- ── Category assignments (object ↔ ontology node) ────────────────
CREATE TABLE IF NOT EXISTS category_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference_media_id UUID REFERENCES reference_media(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    ontology_node_id UUID NOT NULL REFERENCES ontology_nodes(id) ON DELETE CASCADE,
    confidence      FLOAT,              -- ML-assigned confidence [0,1]
    is_confirmed    BOOLEAN DEFAULT FALSE,
    assigned_by     VARCHAR(50) DEFAULT 'auto',  -- 'auto' | 'manual'
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_assignment_target CHECK (
        (reference_media_id IS NOT NULL) OR (document_id IS NOT NULL)
    )
);

CREATE INDEX idx_assignments_media ON category_assignments(reference_media_id);
CREATE INDEX idx_assignments_doc   ON category_assignments(document_id);
CREATE INDEX idx_assignments_node  ON category_assignments(ontology_node_id);

-- Full-text search index on documents
CREATE INDEX idx_documents_text_trgm ON documents USING gin (raw_text gin_trgm_ops);
