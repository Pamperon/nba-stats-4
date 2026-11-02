"""Execute the permission migration against isolated PGlite, never production."""
from pathlib import Path
import re
from check_tracking_db import Database


def main():
    root=Path(__file__).resolve().parents[1]
    migration=next((root/'supabase/migrations').glob('*_restrict_client_table_privileges.sql')).read_text()
    rls=next((root/'supabase/migrations').glob('*_enable_private_application_rls.sql')).read_text()
    tables=re.findall(r'public\.(nba_[a-z0-9_]+)',migration)
    assert len(set(tables))==16
    db=Database()
    try:
        for role in ('anon','authenticated','service_role'):
            db.query('CREATE ROLE '+role+(' BYPASSRLS' if role=='service_role' else ''))
        for table in tables:
            db.query('CREATE TABLE public.'+table+' (id integer)')
            db.query('GRANT ALL ON public.'+table+' TO anon, authenticated, service_role')
        db.query('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role')
        statements=[s.strip() for s in re.sub(r'--[^\n]*','',migration+'\n'+rls).split(';') if s.strip()]
        for _ in range(2):
            for statement in statements:db.query(statement)
        db.query('CREATE TABLE public.future_security_test (id integer)')
        for table in tables+['future_security_test']:
            for role in ('anon','authenticated'):
                result=db.query("SELECT has_table_privilege(%s,%s,%s)",
                                (role,'public.'+table,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
                assert result==[(False,)],(role,table,result)
            assert db.query("SELECT has_table_privilege('service_role',%s,'SELECT')",('public.'+table,))==[(True,)]
            db.query('INSERT INTO public.'+table+' VALUES (1)')
            assert db.query('SELECT id FROM public.'+table)==[(1,)]
        for table in tables:
            assert db.query('SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass',('public.'+table,))==[(True,)]
        # Even an accidental SELECT grant cannot expose private rows via RLS.
        db.query('GRANT SELECT ON public.nba_scan_snapshots TO anon')
        db.query('SET ROLE anon')
        assert db.query('SELECT id FROM public.nba_scan_snapshots')==[]
        db.query('RESET ROLE')
        db.query('SET ROLE service_role')
        assert db.query('SELECT id FROM public.nba_scan_snapshots')==[(1,)]
        db.query('RESET ROLE')
        print('Database security OK: client grants denied, RLS enforced, server access preserved')
    finally:db.close()


if __name__=='__main__':main()
