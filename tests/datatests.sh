#!/bin/bash -eux

python -m pgtoolkit.hba data/pg_hba.conf
! python -m pgtoolkit.hba data/pg_hba_bad.conf
