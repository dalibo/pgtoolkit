#!/bin/bash -eux

python -m pgtoolkit.hba data/pg_hba.conf
! (python -m pgtoolkit.hba data/pg_hba_bad.conf && exit 1)
python -m pgtoolkit.pgpass data/pgpass
! (python -m pgtoolkit.pgpass data/pgpass_bad && exit 1)
