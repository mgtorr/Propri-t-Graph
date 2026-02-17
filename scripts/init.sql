-- PropriétéGraph database initialization
-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Full-text search configuration for French
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'french'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION french (COPY = pg_catalog.french);
    END IF;
END$$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE propriete_graph TO propriete;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO propriete;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO propriete;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO propriete;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO propriete;
