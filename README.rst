####################################
 Postgres Cluster Support in Python
####################################

| |CircleCI| |Codecov| |RTD|


`pgtoolkit` provides implementations to manage various file formats in Postgres
cluster. Currently:

- `pg_hba.conf` : render, validate and align columns.
- `.pgpass` : render, validate and sort lines.


The API in this toolkit must:

- Use only Python stdlib.
- Use Postgres idioms.
- Have full test coverage.
- Run everywhere.


.. |Codecov| image:: https://codecov.io/gh/dalibo/pgtoolkit/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/dalibo/pgtoolkit
   :alt: Code coverage report

.. |CircleCI| image:: https://circleci.com/gh/dalibo/pgtoolkit.svg?style=shield
   :target: https://circleci.com/gh/dalibo/pgtoolkit
   :alt: Continuous Integration report

.. |RTD| image:: https://readthedocs.org/projects/pgtoolkit/badge/?version=latest
   :target: https://pgtoolkit.readthedocs.io/en/latest/
   :alt: Documentation
