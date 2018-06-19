# coding: utf-8
#
#
#                P O S T G R E S   L O G   P A R S E R
#
#
# Postgres logs are still the best sources of information on what's going on in
# a cluster. Here is a parser to exploit Postgres log records from Python.
#
# Parsing logs is tricky because format is varying accros configuration and
# performance is important.
#
# The fastest code is NOOP. Thus, the parser allows you to filter records as
# soon as possible. The parser has several distinct stages and records can be
# filter after each stages.
#
# 1. Split prefix, severity and message, determine message type.
# 2. Extract and decode prefix data
# 3. Extract and decode message data.
#
# cf. https://www.postgresql.org/docs/10/static/runtime-config-logging.html for
# details on logging fields and configuration.
#
# You can use this module to dump logs as JSON:
#
#     python -m pgtoolkit.log <log_line_prefix> [<filename>]
#

from __future__ import print_function

from datetime import datetime
import json
import logging
import os
import re
import sys
from datetime import timedelta

from ._helpers import open_or_stdin
from ._helpers import Timer


logger = logging.getLogger(__name__)


def parse(fo, prefix_fmt, filters=None):
    # This is the main entry point. Parses log lines and yield Record objects
    # or UnknownData.
    #
    # prefix_fmt is exactly the value of log_line_prefix in postgresql.conf.
    # filters is an object like NoopFilters() class.

    prefix_parser = PrefixParser.from_configuration(prefix_fmt).parse
    filters = filters or NoopFilters()
    for group in group_lines(fo):
        try:
            record = Record.parse_stage1(group)
            if filters.stage1(record):
                continue
            record.parse_stage2(prefix_parser)
            if filters.stage2(record):
                continue
            record.parse_stage3()
            if filters.stage3(record):
                continue
        except UnknownData as e:
            yield e
        else:
            yield record


def group_lines(lines, cont='\t'):
    # Group continuation lines according to continuation prefix. Yield a list
    # on lines supposed to belong to the same log record.

    group = []
    for line in lines:
        if not line.startswith(cont) and group:
            yield group
            group = []
        group.append(line)

    if group:
        yield group


def parse_datetime(raw):
    match = PrefixParser._datetime_re.match(raw)
    if not match:
        raise ValueError("%s is not a known date" % raw)
    infos = []
    for v in match.groups()[:-1]:
        infos.append(0 if v is None else int(v))
    tz = match.group('timezone')
    if tz != 'UTC':
        # We need tzdata for that.
        raise ValueError("Timezone %s is not managed" % tz)
    return datetime(*infos)


def parse_epoch(raw):
    epoch, ms = raw.split('.')
    return (
        datetime.utcfromtimestamp(int(epoch)) +
        timedelta(microseconds=int(ms))
    )


class UnknownData(Exception):
    # UnknownData object is an exception to be throwable.

    def __init__(self, lines):
        self.lines = lines

    def __str__(self):
        return "Unknown data:\n%s" % (''.join(self.lines),)


class NoopFilters(object):
    # Filters are grouped in an object to simplify the definition of a
    # filtering policy. We can implement simple filter or heavy parameterize
    # filtering policy from this API.
    #
    # If a filter method returns True, the record processing stops and the
    # record is dropped.

    def stage1(self, record):
        pass

    def stage2(self, record):
        pass

    def stage3(self, record):
        pass


class PrefixParser(object):
    # PrefixParser extracts information from the beginning of each log lines,
    # parameterized by log_line_prefix.
    #
    # cf.
    # https://www.postgresql.org/docs/10/static/runtime-config-logging.html#GUC-LOG-LINE-PREFIX

    _datetime_re = re.compile(
        r'(?P<year>\d{4})-(?P<month>[01]\d)-(?P<day>[0-3]\d)'
        r' '
        r'(?P<hour>[012]\d):(?P<minute>[0-6]\d):(?P<second>[0-6]\d)'
        r'(?:\.(?P<microsecond>\d+))?'
        r' '
        r'(?P<timezone>\w+)'
    )

    _datetime_pat = r'\d{4}-[01]\d-[0-3]\d [012]\d:[0-6]\d:[0-6]\d'
    # Pattern map of Status informations.
    _status_pat = dict(
        # Application name
        a=r'(?P<application>\[unknown\]|\w+)?',
        # Session ID
        c=r'(?P<session>\[unknown\]|[0-9a-f.]+)',
        # Database name
        d=r'(?P<database>\[unknown\]|\w+)?',
        # SQLSTATE error code
        e=r'(?P<error>\d+)',
        # Remote host name or IP address
        h=r'(?P<remote_host>\[local\]|\[unknown\]|[a-z0-9_-]+|[0-9.:]+)?',
        # Command tag: type of session's current command
        i=r'(?P<command_tag>\w+)',
        # Number of the log line for each session or process, starting at 1.
        l=r'(?P<line_num>\d+)',  # noqa
        # Time stamp with milliseconds
        m=r'(?P<timestamp_ms>' + _datetime_pat + '.\d{3} [A-Z]{2,5})',
        # Time stamp with milliseconds (as a Unix epoch)
        n=r'(?P<epoch>\d+\.\d+)',
        # Process ID
        p=r'(?P<pid>\d+)',
        # Remote host name or IP address, and remote port
        r=r'(?P<remote_host_r>\[local\]|\[unknown\]|[a-z0-9_-]+|[0-9.:]+\((?P<remote_port>\d+)\))?',  # noqa
        # Process start time stamp
        s=r'(?P<start>' + _datetime_pat + ' [A-Z]{2,5})',
        # Time stamp without milliseconds
        t=r'(?P<timestamp>' + _datetime_pat + ' [A-Z]{2,5})',
        # User name
        u=r'(?P<user>\[unknown\]|\w+)?',
        # Virtual transaction ID (backendID/localXID)
        v=r'(?P<virtual_xid>\d+/\d+)',
        # Transaction ID (0 if none is assigned)
        x=r'(?P<xid>\d+)',
    )
    # re to search for %… in log_line_prefix.
    _format_re = re.compile(r'%([' + ''.join(_status_pat.keys()) + '])')
    # re to find %q separator in log_line_prefix.
    _q_re = re.compile(r'(?<!%)%q')

    _casts = {
        'epoch': parse_epoch,
        'line_num': int,
        'pid': int,
        'remote_port': int,
        'start': parse_datetime,
        'timestamp': parse_datetime,
        'timestamp_ms': parse_datetime,
        'xid': int,
    }

    @classmethod
    def mkpattern(cls, prefix):
        # Builds a pattern from each known fields.
        segments = cls._format_re.split(prefix)
        for i, segment in enumerate(segments):
            if i % 2:
                segments[i] = cls._status_pat[segment]
            else:
                segments[i] = re.escape(segment)
        return ''.join(segments)

    @classmethod
    def from_configuration(cls, log_line_prefix):
        # Parse log_line_prefix and build a prefix parser from this.
        try:
            fixed, optionnal = cls._q_re.split(log_line_prefix)
        except ValueError:
            fixed, optionnal = log_line_prefix, None

        pattern = cls.mkpattern(fixed)
        if optionnal:
            pattern += r'(?:' + cls.mkpattern(optionnal) + ')?'
        return cls(re.compile(pattern), log_line_prefix)

    def __init__(self, re_, prefix_fmt=None):
        self.re_ = re_
        self.prefix_fmt = prefix_fmt

    def __repr__(self):
        return '<%s \'%s\'>' % (self.__class__.__name__, self.prefix_fmt)

    def parse(self, prefix):
        # Parses the prefix line according to the inner regular expression. If
        # prefix does not match, raises an UnknownData.

        match = self.re_.search(prefix)
        if not match:
            raise UnknownData([prefix])
        fields = match.groupdict()

        self.cast_fields(fields)

        # Ensure remote_host is fed either by %h or %r.
        remote_host = fields.pop('remote_host_r', None)
        if remote_host:
            fields.setdefault('remote_host', remote_host)

        # Ensure timestamp field is fed eiter by %m or %t.
        timestamp_ms = fields.pop('timestamp_ms', None)
        if timestamp_ms:
            fields.setdefault('timestamp', timestamp_ms)

        return fields

    @classmethod
    def cast_fields(cls, fields):
        # In-place cast of values in fields dictionnary.

        for k, v in fields.items():
            if v is None:
                continue
            cast = cls._casts.get(k)
            if cast:
                fields[k] = cast(v)


class Record(object):
    # Log record object.
    #
    # Implements the different parse stages and store status informations.
    #
    # A record is primarily defined as a prefix, a severity and a message.
    # Actually, severity is mixed with message type. For example, a HINT:
    # message has the same severity as LOG: (see csvlog output to compare).
    # Thus we can determine easily message type as this stage.
    #
    # Once prefix, severity and message are splitted, we parse prefix from
    # log_line_prefix parameter. Prefix can give a lot of information for
    # filtering.
    #
    # Finally, we parse the message to extract information such as statement,
    # hint, duration, execution plan, etc. depending on the type.
    #
    # All a these stages are separated to allow marshalling to apply filter
    # between each stage.
    #

    # This actually mix severities and message type since they are in the same
    # field.
    _severities = [
        'CONTEXT',
        'DETAIL',
        'ERROR',
        'FATAL',
        'HINT',
        'INFO',
        'LOG',
        'NOTICE',
        'PANIC',
        'QUERY',
        'STATEMENT',
        'WARNING',
    ]
    _stage1_re = re.compile('(DEBUG[1-5]|' + '|'.join(_severities) + '):  ')

    _types_prefixes = {
        'duration: ': 'duration',
        'connection ': 'connection',
        'disconnection': 'connection',
        'automatic analyze': 'analyze',
        'checkpoint ': 'checkpoint',
    }

    @classmethod
    def guess_type(cls, severity, message_start):
        # Guess message type from severity and the first line of the message.

        if severity in ('HINT', 'STATEMENT'):
            return severity.lower()
        for prefix, type_ in cls._types_prefixes.items():
            if message_start.startswith(prefix):
                return type_
        return 'unknown'

    @classmethod
    def parse_stage1(cls, lines):
        # Stage1: split prefix, severity and message.
        try:
            prefix, severity, message0 = cls._stage1_re.split(
                lines[0], maxsplit=1)
        except ValueError:
            raise UnknownData(lines)

        return cls(
            prefix=prefix,
            severity=severity,
            message_type=cls.guess_type(severity, message0),
            message_lines=[message0] + lines[1:],
            raw_lines=lines,
        )

    def __init__(
            self, prefix, severity, message_type='unknown', message_lines=None,
            raw_lines=None, **fields):
        self.prefix = prefix
        self.severity = severity
        self.message_type = message_type
        self.message_lines = message_lines or []
        self.raw_lines = raw_lines or []
        self.__dict__.update(fields)

    def __repr__(self):
        return '<%s %s: %.32s...>' % (
            self.__class__.__name__, self.severity, self.message_lines[0],
        )

    def parse_stage2(self, parse_prefix):
        # Stage 2. Analyze prefix fields

        self.__dict__.update(parse_prefix(self.prefix))

    def parse_stage3(self):
        # Stage 3. Analyze message lines.

        self.message = ''.join([
            l.lstrip('\t').rstrip('\n') for l in self.message_lines
        ])

    def as_dict(self):
        return dict([
            (k, v)
            for k, v in self.__dict__.items()
            if k not in ('raw_lines', 'message_lines', 'prefix')
        ])


class RecordEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(RecordEncoder, self).default(obj)


def main(argv=sys.argv[1:], environ=os.environ):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)5.5s %(message)s',
    )

    argv = argv + ['-']
    log_line_prefix = argv[0]
    counter = 0
    try:
        with open_or_stdin(argv[1]) as fo:
            with Timer() as timer:
                for record in parse(fo, prefix_fmt=log_line_prefix):
                    if isinstance(record, UnknownData):
                        logger.warn("%s", record)
                    else:
                        counter += 1
                        print(json.dumps(record.as_dict(), cls=RecordEncoder))
        logger.info("Parsed %d records in %s.", counter, timer.delta)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if '__main__' == __name__:  # pragma: nocover
    sys.exit(main(argv=sys.argv[1:], environ=os.environ))
