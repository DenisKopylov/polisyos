-- 004_roles_grants.sql
-- Phase 1 step 4: enforce least privilege for application role.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'polisyos_app') THEN
        CREATE ROLE polisyos_app LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA world TO polisyos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA world TO polisyos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.macro_history TO polisyos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agents_snapshot TO polisyos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.run_records TO polisyos_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA world
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO polisyos_app;

ALTER DATABASE polisyos SET app.current_tenant = '00000000-0000-0000-0000-000000000000';

-- IMPORTANT: do not grant BYPASSRLS or SUPERUSER to application role.
