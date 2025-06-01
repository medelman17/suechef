-- PostgreSQL initialization script for SueChef
-- This script ensures the database is properly configured for legal research

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create the legal_research database if it doesn't exist
-- (This is handled by POSTGRES_DB environment variable in Docker)

-- Set up proper text search configuration
-- This helps with full-text search performance for legal documents
ALTER DATABASE legal_research SET default_text_search_config = 'pg_catalog.english';

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE legal_research TO postgres;