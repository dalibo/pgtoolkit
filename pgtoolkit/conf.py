# -*- coding: utf-8 -*-
"""\
.. currentmodule:: pgtoolkit.conf

This module implements ``postgresql.conf`` file format. This is the same format
for ``recovery.conf``. The main entry point of the API is :func:`parse`. The
module can be used as a CLI script.


API Reference
-------------

.. autofunction:: parse
.. autoclass:: Configuration


Using as a CLI Script
---------------------

You can use this module to dump a configuration file as JSON object

.. code:: console

    $ python -m pgtoolkit.conf postgresql.conf | jq .
    {
      "lc_monetary": "fr_FR.UTF8",
      "datestyle": "iso, dmy",
      "log_rotation_age": "1d",
      "log_min_duration_statement": "3s",
      "log_lock_waits": true,
      "log_min_messages": "notice",
      "log_directory": "log",
      "port": 5432,
      "log_truncate_on_rotation": true,
      "log_rotation_size": 0
    }
    $

"""


from __future__ import print_function

import json
from ast import literal_eval
try:  # pragma: nocover_py26
    from collections import OrderedDict
except ImportError:  # pragma: nocover_py3
    # On python 2.6, order is not preserved
    OrderedDict = dict
import re
import sys
from datetime import timedelta


from ._helpers import JSONDateEncoder
from ._helpers import open_or_stdin


def parse(fo):
    """Parse a configuration file.

    The parser tries to return Python object corresponding to value, based on
    some heuristics. booleans, octal number, decimal integers and floating
    point numbers are parsed. Multiplier units like kB or MB are applyied and
    you get an int. Interval value like ``3s`` are returned as
    :class:`datetime.timedelta`.

    In case of doubt, the value is kept as a string. It's up to you to enforce
    format.

    :param fo: A line iterator such as a file-like object
    :returns: A :class:`Configuration` containing parsed configuration.

    """
    conf = Configuration()
    conf.parse(fo)
    return conf


MEMORY_MULTIPLIERS = {
    'kB': 1024,
    'MB': 1024 * 1024,
    'GB': 1024 * 1024 * 1024,
    'TB': 1024 * 1024 * 1024 * 1024,
}
_memory_re = re.compile(r'^\s*(?P<number>\d+)\s*(?P<unit>[kMGT]B)\s*$')
TIMEDELTA_ARGNAME = {
    'ms': 'milliseconds',
    's': 'seconds',
    'min': 'minutes',
    'h': 'hours',
    'd': 'days',
}
_timedelta_re = re.compile(r'^\s*(?P<number>\d+)\s*(?P<unit>ms|s|min|h|d)\s*$')


def parse_value(raw):
    # Ref.
    # https://www.postgresql.org/docs/current/static/config-setting.html#CONFIG-SETTING-NAMES-VALUES

    if raw.startswith("'"):
        try:
            raw = literal_eval(raw)
        except SyntaxError as e:
            raise ValueError(str(e))

    if raw.startswith('0'):
        try:
            return int(raw, base=8)
        except ValueError:
            pass

    m = _memory_re.match(raw)
    if m:
        unit = m.group('unit')
        mul = MEMORY_MULTIPLIERS[unit]
        return int(m.group('number')) * mul

    m = _timedelta_re.match(raw)
    if m:
        unit = m.group('unit')
        arg = TIMEDELTA_ARGNAME[unit]
        kwargs = {arg: int(m.group('number'))}
        return timedelta(**kwargs)

    elif raw in ('true', 'yes', 'on'):
        return True
    elif raw in ('false', 'no', 'off'):
        return False
    else:
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw


class Configuration(object):
    r"""Holds a parsed configuration.

    You can access parameter using attribute or dictionnary syntax.

    >>> conf = parse(['port=5432\n', 'pg_stat_statement.min_duration = 3s\n'])
    >>> conf.port
    5432
    >>> conf['pg_stat_statement.min_duration']
    datetime.timedelta(0, 3)
    """  # noqa
    _parameter_re = re.compile(
        r'^(?P<name>[a-z_.]+)(?: +(?!=)| *= *)(?P<value>.*?)'
        '[\s\t]*'
        r'(?P<comment>#.*)?$'
    )

    def __init__(self):
        self.lines = []
        self.entries = OrderedDict()

    def parse(self, fo):
        for raw_line in fo:
            self.lines.append(raw_line)
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            m = self._parameter_re.match(line)
            if not m:
                raise ValueError("Bad line: %r." % raw_line)
            entry = m.groupdict()
            entry['value'] = parse_value(entry['value'])
            entry['raw_line'] = raw_line

            self.entries[entry['name']] = entry

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, key):
        return self.entries[key]['value']

    def as_dict(self):
        return dict([(k, v['value']) for k, v in self.entries.items()])


def _main(argv):  # pragma: nocover
    argv = argv or ['-']
    try:
        with open_or_stdin(argv[0]) as fo:
            conf = parse(fo)
        print(json.dumps(conf.as_dict(), cls=JSONDateEncoder, indent=2))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':  # pragma: nocover
    exit(_main(sys.argv[1:]))
