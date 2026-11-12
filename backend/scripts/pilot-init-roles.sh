#!/bin/sh
# Invoked ONLY on initial creation of the dedicated pilot volume.
set -eu
: "${PILOT_APP_PASSWORD:?PILOT_APP_PASSWORD is required}"
# psql variable quoting ensures passwords are SQL literals, not executable SQL.
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set="pilot_app_password=$PILOT_APP_PASSWORD" <<'SQL'
REVOKE ALL ON DATABASE dwi_local_pilot FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE ROLE pilot_app LOGIN PASSWORD :'pilot_app_password';
GRANT CONNECT ON DATABASE dwi_local_pilot TO pilot_app;
GRANT USAGE, CREATE ON SCHEMA public TO pilot_app;
SQL
