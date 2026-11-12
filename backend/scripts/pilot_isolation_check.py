"""Synthetic-only permission and isolation check for the local pilot PostgreSQL.

Requires DWI_PILOT_DATABASE_URL, DATABASE_URL, and both running local servers.
Never reads real records or prints credentials.
"""

import os

from sqlalchemy import create_engine, text

from app.ingestion.pilot_policy import require_private_pilot_database


pilot_url = require_private_pilot_database()
app_url = os.environ.get("DATABASE_URL")
if not app_url:
    raise SystemExit("Set DATABASE_URL to the main local development database for this check.")

def inspect(url: str):
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            return conn.execute(text(
                "SELECT current_database(), current_user, "
                "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user)"
            )).one()
    finally:
        engine.dispose()

pilot_db, pilot_user, pilot_superuser = inspect(pilot_url)
main_db, main_user, _ = inspect(app_url)
assert pilot_db == "dwi_local_pilot"
assert pilot_user == "pilot_app"
assert pilot_superuser is False
assert main_db != pilot_db
assert main_user != pilot_user
print("Pilot PostgreSQL identity and non-superuser verification: PASS")

# Negative checks deliberately use a credential pair against the wrong
# *server*. SQLAlchemy URLs differ by host port and username/password.
from sqlalchemy.engine import make_url

pilot = make_url(pilot_url)
main = make_url(app_url)

def must_refuse(url):
    try:
        inspect(url.render_as_string(hide_password=False))
    except Exception:
        return
    raise AssertionError("Cross-environment credential isolation failed.")

must_refuse(pilot.set(username=main.username, password=main.password))
must_refuse(main.set(username=pilot.username, password=pilot.password))
print("Cross-environment database credentials refused: PASS")
