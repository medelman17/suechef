"""Database schema definitions for the unified legal MCP system."""

POSTGRES_SCHEMA = """
-- Events table for timeline management
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    description TEXT NOT NULL,
    parties JSONB DEFAULT '[]'::jsonb,
    document_source TEXT,
    excerpts TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    significance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', 
            coalesce(description, '') || ' ' || 
            coalesce(excerpts, '') || ' ' || 
            coalesce(significance, '') || ' ' ||
            coalesce(document_source, '')
        )
    ) STORED
);

-- Snippets table for legal precedents
CREATE TABLE IF NOT EXISTS snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citation TEXT NOT NULL,
    key_language TEXT NOT NULL,
    tags JSONB DEFAULT '[]'::jsonb,
    context TEXT,
    case_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', 
            coalesce(citation, '') || ' ' || 
            coalesce(key_language, '') || ' ' || 
            coalesce(context, '') || ' ' ||
            coalesce(case_type, '')
        )
    ) STORED
);

-- Manual links between events and snippets
CREATE TABLE IF NOT EXISTS manual_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    snippet_id UUID REFERENCES snippets(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, snippet_id, relationship_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_parties ON events USING GIN (parties);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_events_search ON events USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_snippets_citation ON snippets(citation);
CREATE INDEX IF NOT EXISTS idx_snippets_tags ON snippets USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_snippets_search ON snippets USING GIN (search_vector);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_events_updated_at BEFORE UPDATE
    ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_snippets_updated_at BEFORE UPDATE
    ON snippets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

QDRANT_COLLECTIONS = {
    "legal_events": {
        "size": 1536,  # OpenAI embedding size
        "distance": "Cosine"
    },
    "legal_snippets": {
        "size": 1536,
        "distance": "Cosine"
    }
}