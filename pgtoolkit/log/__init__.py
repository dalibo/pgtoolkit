"""\
.. currentmodule:: pgtoolkit.log

Postgres logs are still the most comprehensive source of information on what's
going on in a cluster. :mod:`pgtoolkit.log` provides a parser to exploit
efficiently Postgres log records from Python.

Parsing logs is tricky because format varies accross configurations. Also
performance is important while logs can contain thousands of records.


Configuration
-------------

Postgres log records have a prefix, configured with ``log_line_prefix`` cluster
setting. When analyzing a log file, you must known the ``log_line_prefix``
value used to generate the records.

Postgres can emit more message for your needs. See `Error Reporting and Logging
section
<https://www.postgresql.org/docs/current/static/runtime-config-logging.html>`_
if PostgreSQL documentation for details on logging fields and message type.


Performance
-----------

The fastest code is NOOP. Thus, the parser allows you to filter records as soon
as possible. The parser has several distinct stages. After each stage, the
parser calls a filter to determine whether to stop record processing. Here are
the stages in processing order :

1. Split prefix, severity and message, determine message type.
2. Extract and decode prefix data
3. Extract and decode message data.


Limitations
-----------

:mod:`pgtoolkit.log` does not manage opening and uncompressing logs. It only
accepts a line reader iterator that loops log lines. The same way,
:mod:`pgtoolkit.log` does not manage to start analyze at a specific position in
a file.

:mod:`pgtoolkit.log` does not gather record set such as ``ERROR`` and
following ``HINT`` record. It's up to the application to make sense of record
sequences.

:mod:`pgtoolkit.log` does not analyze log records. It's just a parser, a
building block to write a log analyzer in your app.


API Reference
-------------

Here are the few functions and classes used to parse and access log records.

.. autofunction:: parse
.. autoclass:: LogParser
.. autoclass:: PrefixParser
.. autoclass:: Record
.. autoclass:: UnknownData
.. autoclass:: NoopFilters


Example
-------

Here is a sample structure of code parsing a plain log file.

.. code-block:: python

    with open('postgresql.log') as fo:
        for r in parse(fo, prefix_fmt='%m [%p]'):
            if isinstance(r, UnknownData):
                "Process unknown data"
            else:
                "Process record"



Using :mod:`pgtoolkit.log` as a script
--------------------------------------

You can use this module to dump logs as JSON using the following usage::

    python -m pgtoolkit.log <log_line_prefix> [<filename>]

:mod:`pgtoolkit.log` serializes each record as a JSON object on a single line.

.. code:: console

    $ python -m pgtoolkit.log '%m [%p]: [%l-1] app=%a,db=%d%q,client=%h,user=%u ' data/postgresql.log
    {"severity": "LOG", "timestamp": "2018-06-15T10:49:31.000144", "message_type": "connection", "line_num": 2, "remote_host": "[local]", "application": "[unknown]", "user": "postgres", "message": "connection authorized: user=postgres database=postgres", "database": "postgres", "pid": 8423}
    {"severity": "LOG", "timestamp": "2018-06-15T10:49:34.000172", "message_type": "connection", "line_num": 1, "remote_host": "[local]", "application": "[unknown]", "user": "[unknown]", "message": "connection received: host=[local]", "database": "[unknown]", "pid": 8424}

"""  # noqa

from .parser import (
    LogParser,
    NoopFilters,
    PrefixParser,
    Record,
    UnknownData,
    parse,
)


__all__ = [
    o.__name__  # type: ignore[attr-defined]
    for o in [
        LogParser,
        NoopFilters,
        PrefixParser,
        Record,
        UnknownData,
        parse,
    ]
]
