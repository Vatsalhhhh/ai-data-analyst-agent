-- Read-only role used by the application at query time. Keeping the
-- runtime path on a SELECT-only grant means a bug (or a prompt-injected
-- query from the LLM path) can't mutate or drop data.
--
-- The password is set from an environment variable by db/load.py at apply
-- time; the placeholder below is only used if this file is run manually.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analyst_ro') THEN
        CREATE ROLE analyst_ro WITH LOGIN PASSWORD 'changeme_readonly';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE analyst_db TO analyst_ro;
GRANT USAGE ON SCHEMA public TO analyst_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyst_ro;

-- Make sure tables created later are also readable by the role.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analyst_ro;
