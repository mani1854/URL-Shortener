-- scripts/init_db.sql
-- Executed once by the Postgres Docker container on first boot.
-- Creates any required extensions and initial objects.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for future full-text / similarity search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
