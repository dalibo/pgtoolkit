# Postgres Cluster Support in Python

`pgtoolkit` provides implementations to manage various file formats in Postgres
cluster. Currently:

- `pg_hba.conf` : render, validate and align columns.
- `.pgpass` : render, validate and sort lines.


The API in this toolkit must:

- Use only Python stdlib.
- Use Postgres idioms.
- Have full test coverage.
- Run everywhere.
