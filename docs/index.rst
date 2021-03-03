####################################
 Postgres Cluster Support in Python
####################################

pgtoolkit is a Python library providing API to interact with various PostgreSQL
file formats, offline. Namely:

* :mod:`postgresql.conf <pgtoolkit.conf>`
* :mod:`pg_hba.conf <pgtoolkit.hba>`
* :mod:`.pgpass <pgtoolkit.pgpass>`
* :mod:`pg_service.conf <pgtoolkit.service>`
* :mod:`logs <pgtoolkit.log>`

It also provides a Python API for calling pg_ctl_ commands in :mod:`ctl
<pgtoolkit.ctl>` module.

.. _pg_ctl: https://www.postgresql.org/docs/current/app-pg-ctl.html

Quick installation
------------------

Just use PyPI as any regular Python project:

.. code:: console

    $ pip install --pre pgtoolkit


Support
-------

If you need support for ``pgtoolkit``, just drop an `issue on
GitHub <https://github.com/dalibo/pgtoolkit/issues/new>`__!


Project name
------------

There is a homonym project by @grayhemp since September 2013:
`PgToolkit <https://github.com/grayhemp/pgtoolkit>`__.
``grayhemp/PgToolkit`` is a single tool projet, thus *toolkit* is
misleading. Also, as of August 2018, it is inactive for 3 years.

There is no Python library named ``pgtoolkit``. There is no CLI program
named ``pgtoolkit``. There is no ``pgtoolkit`` package. Considering
this, ``pgtoolkit`` was chosen for this project.

Please file a `new issue <https://github.com/dalibo/pgtoolkit/issues/new>`_ if
you have feedback on project name.
