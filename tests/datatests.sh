#!/bin/bash -eux

python -m pgtoolkit.hba data/pg_hba.conf
! (python -m pgtoolkit.hba data/pg_hba_bad.conf && exit 1)

python -m pgtoolkit.pgpass data/pgpass
! (python -m pgtoolkit.pgpass data/pgpass_bad && exit 1)

python -m pgtoolkit.service data/pg_service.conf
! (python -m pgtoolkit.service data/pg_service_bad.conf && exit 1)

logscript=pgtoolkit.log
python -m $logscript '%m [%p]: [%l-1] app=%a,db=%d%q,client=%h,user=%u ' data/postgresql.log
scripts/profile-log

python -m pgtoolkit.conf data/postgres.conf
