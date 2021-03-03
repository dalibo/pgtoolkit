####################################
 Postgres Cluster Support in Python
####################################

| |CircleCI| |Codecov| |RTD|


``pgtoolkit`` provides implementations to manage various file formats in Postgres
cluster. Currently:

- ``postgresql.conf``: read, edit, save.
- ``pg_hba.conf``: render, validate and align columns.
- ``.pgpass``: render, validate and sort lines.
- ``pg_service.conf``: find, read, edit, render.
- Cluster logs.

It also provides a Python API for calling pg_ctl_ commands.

.. _pg_ctl: https://www.postgresql.org/docs/current/app-pg-ctl.html


.. code::

   import sys

   from pgtoolkit.hba import parse


   with open('pg_hba.conf') as fo:
       hba = parse(fo)

   hba.write(sys.stdout)


The API in this toolkit must:

- Use only Python stdlib.
- Use Postgres idioms.
- Have full test coverage.
- Run everywhere.


Support
-------

`pgtoolkit <https://github.com/dalibo/pgtoolkit>`_ home on GitHub is the unique
way of interacting with developers. Feel free to open an issue to get support.


.. |Codecov| image:: https://codecov.io/gh/dalibo/pgtoolkit/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/dalibo/pgtoolkit
   :alt: Code coverage report

.. |CircleCI| image:: https://circleci.com/gh/dalibo/pgtoolkit.svg?style=shield
   :target: https://circleci.com/gh/dalibo/pgtoolkit
   :alt: Continuous Integration report

.. |RTD| image:: https://readthedocs.org/projects/pgtoolkit/badge/?version=latest
   :target: https://pgtoolkit.readthedocs.io/en/latest/
   :alt: Documentation
