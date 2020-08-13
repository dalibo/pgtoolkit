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


import json
from ast import literal_eval
from collections import OrderedDict
import re
import sys
from datetime import timedelta
from typing import Dict, IO, Iterable, List, Optional, Union

from ._helpers import JSONDateEncoder
from ._helpers import open_or_stdin
from ._helpers import open_or_return


def parse(fo: Union[str, IO[str]]) -> "Configuration":
    """Parse a configuration file.

    The parser tries to return Python object corresponding to value, based on
    some heuristics. booleans, octal number, decimal integers and floating
    point numbers are parsed. Multiplier units like kB or MB are applyied and
    you get an int. Interval value like ``3s`` are returned as
    :class:`datetime.timedelta`.

    In case of doubt, the value is kept as a string. It's up to you to enforce
    format.

    :param fo: A line iterator such as a file-like object or a path.
    :returns: A :class:`Configuration` containing parsed configuration.

    """
    conf = Configuration()
    with open_or_return(fo) as fo:
        conf.parse(fo)
        conf.path = getattr(fo, 'name', None)
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


Value = Union[str, bool, float, int, timedelta]


def parse_value(raw: str) -> Value:
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


class Entry:
    # Holds the parsed representation of a configuration entry line.
    #
    # This includes the comment.

    def __init__(
        self,
        name: str,
        value: Value,
        comment: Optional[str] = None,
        raw_line: Optional[str] = None,
    ) -> None:
        self.name = name
        self.value = value
        self.comment = comment
        # Store the raw_line to track the position in the list of lines.
        self.raw_line = raw_line

    def __repr__(self) -> str:
        return '<%s %s=%s>' % (self.__class__.__name__, self.name, self.value)

    _minute = 60
    _hour = 60 * _minute
    _day = 24 * _hour

    _timedelta_unit_map = [
        ('d', _day),
        ('h', _hour),
        # The space before 'min' is intentionnal. I find '1 min' more readable
        # than '1min'.
        (' min', _minute),
        ('s', 1),
    ]

    def serialize(self) -> Union[int, str]:
        # This is the reverse of parse_value.
        value = self.value
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        elif isinstance(value, int):
            for unit in None, 'kB', 'MB', 'GB', 'TB':
                if value % 1024:
                    break
                value = value // 1024
            if unit:
                value = "'%s %s'" % (value, unit)
        elif isinstance(value, str):
            if ' ' in value or "'" in value:
                value = "'%s'" % value.replace("'", r"\'")
        elif isinstance(value, timedelta):
            seconds = value.days * self._day + value.seconds
            if value.microseconds:
                unit = ' ms'
                value = seconds * 1000 + value.microseconds // 1000
            else:
                for unit, mod in self._timedelta_unit_map:
                    if seconds % mod:
                        continue
                    value = seconds // mod
                    break
            value = "'%s%s'" % (value, unit)
        else:
            value = str(value)
        return value

    def __str__(self) -> str:
        line = '%(name)s = %(value)s' % dict(
            name=self.name, value=self.serialize())
        if self.comment:
            line += '  # ' + self.comment
        return line


class Configuration:
    r"""Holds a parsed configuration.

    You can access parameter using attribute or dictionnary syntax.

    >>> conf = parse(['port=5432\n', 'pg_stat_statement.min_duration = 3s\n'])
    >>> conf.port
    5432
    >>> conf.port = 5433
    >>> conf.port
    5433
    >>> conf['port'] = 5434
    >>> conf.port
    5434
    >>> conf['pg_stat_statement.min_duration'].total_seconds()
    3.0

    .. attribute:: path

        Path to a file. Automatically set when calling :func:`parse` with a path
        to a file. This is default target for :meth:`save`.

    .. automethod:: save

    """  # noqa
    lines: List[str]
    entries: Dict[str, Entry]
    path: Optional[str]

    _parameter_re = re.compile(
        r'^(?P<name>[a-z_.]+)(?: +(?!=)| *= *)(?P<value>.*?)'
        '[\\s\t]*'
        r'(?P<comment>#.*)?$'
    )

    # Internally, lines property contains an updated list of all comments and
    # entries serialized. When adding a setting or updating an existing one,
    # the serialized line is updated accordingly. This allows to keep comments
    # and serialize only what's needed. Other lines are just written as-is.

    def __init__(self) -> None:
        self.__dict__.update(dict(
            lines=[],
            entries=OrderedDict(),
            path=None,
        ))

    def parse(self, fo: Iterable[str]) -> None:
        for raw_line in fo:
            self.lines.append(raw_line)
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            m = self._parameter_re.match(line)
            if not m:
                raise ValueError("Bad line: %r." % raw_line)
            kwargs = m.groupdict()
            value = parse_value(kwargs.pop('value'))
            entry = Entry(value=value, raw_line=raw_line, **kwargs)
            self.entries[entry.name] = entry

    def __getattr__(self, name: str) -> Value:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Value) -> None:
        if name in self.__dict__:
            self.__dict__[name] = value
        else:
            self[name] = value

    def __getitem__(self, key: str) -> Value:
        return self.entries[key].value

    def __setitem__(self, key: str, value: Value) -> None:
        if key in self.entries:
            e = self.entries[key]
            e.value = value
            # Update serialized entry.
            assert e.raw_line is not None
            old_line = e.raw_line
            e.raw_line = str(e) + '\n'
            lineno = self.lines.index(old_line)
            self.lines[lineno:lineno+1] = [e.raw_line]
        else:
            self.entries[key] = e = Entry(name=key, value=value)
            # Append serialized line.
            e.raw_line = str(e) + '\n'
            self.lines.append(e.raw_line)

    def as_dict(self) -> Dict[str, Value]:
        return dict([(k, v.value) for k, v in self.entries.items()])

    def save(self, fo: Optional[Union[str, IO[str]]] = None) -> None:
        """Write configuration to a file.

        Configuration entries order and comments are preserved.

        :param fo: A path or file-like object. Required if :attr:`path` is
            None.

        """
        with open_or_return(fo or self.path, mode='w') as fo:
            for line in self.lines:
                fo.write(line)


def _main(argv: List[str]) -> int:  # pragma: nocover
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
