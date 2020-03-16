# coding: utf-8
import codecs
import re
from datetime import datetime


def parse_syslog_datetime(raw, fmt="%b %d %H:%M:%S", year=None, tzinfo=None):
    """Parse an incomplete timestamp from syslog.

    :param fmt: Date format as documented by strptime from standard library.
                Default value is rsyslog default timestamp format.
    :param year: Year override for timestamp without year.
    :param tzinfo: Timezone override for timestamp withour timezone info.
    :returns: A datetime object.

    """
    date = datetime.strptime(raw, fmt)
    if year:
        date = date.replace(year=year)
    if tzinfo:
        date = date.replace(tzinfo=tzinfo)
    return date


class SyslogPreprocessor(object):
    """Restore PostgreSQL log lines from syslog records
    """
    def __init__(self, syslog_sequence_numbers=True, date_parser=None):
        """
        :param syslog_sequence_numbers: The value of PostgreSQL setting
            syslog_sequence_numbers.
        :param date_parser: A callable parsing a string and returning a
            datetime object.
        """
        self.date_parser = date_parser
        self._re = re.compile(self.build_prefix_re(
            syslog_sequence_numbers=syslog_sequence_numbers
        ))

    def build_prefix_re(self, syslog_sequence_numbers):
        pattern = (
            r"^"
            r"(?P<timestamp>[a-zA-Z0-9: -]+) "
            r"(?P<hostname>[a-z0-9_-]+) "
            r"(?P<syslog_ident>[a-z0-9_-]+)"
            r"\[(?P<pid>\d+)\]: "
        )

        if syslog_sequence_numbers:
            pattern += r"\[(?P<seq>\d+)-(?P<chunk_nr>\d+)\] "
        else:
            pattern += r"\[(?P<chunk_nr>\d+)\] "
        return pattern

    def process(self, lines):
        """Preprocess syslog lines for parsing

        If a line matches syslog prefix, the preprocessor wraps it unprefixed
        with :class:`SyslogLine` object. This object hold decoded line as
        PostgreSQL would have written it to a log file as well as syslog
        metadata (timestamp, pid, etc.)

        :param lines: A line iterator such as a file object.
        :returns: Yields each :class:`SyslogLine` or plain line.

        """
        for line in lines:
            m = self._re.match(line)
            if m:
                message = line[len(m.group(0)):]
                # Avoid codecs registry and use impl directly.
                message, _ = octal_decode(message)
                line = SyslogLine(
                    message,
                    date_parser=self.date_parser,
                    **m.groupdict()
                )
            yield line


class SyslogLine(str):
    def __new__(cls, message, date_parser=None, **kw):
        # str.__init__ signature is fixed. Let's use __new__.
        self = super(SyslogLine, cls).__new__(cls, message)
        self.__dict__.update(kw)
        self.date_parser = date_parser or parse_syslog_datetime
        return self

    def parse_stage2(self, record):
        if not hasattr(record, 'pid'):
            record.pid = int(self.pid)
        if not hasattr(record, 'timestamp'):
            record.timestamp = self.date_parser(self.timestamp)


_octal_char = re.compile('#([0-7]{3})')


def octal_decode(text):
    chunks = _octal_char.split(text)
    out = []
    for i, item in enumerate(chunks):
        is_chunk = not i % 2
        if is_chunk:
            out.append(item)
        else:
            out.append(chr(int(item, base=8)))
    return ''.join(out), len(text)


def octal_encode(text):
    out = []
    for c in text:
        codepoint = ord(c)
        if codepoint <= 31:
            out.append("#%03o" % codepoint)
        else:
            out.append(c)
    return ''.join(out), len(text)


def octal_search(encoding_name):
    return codecs.CodecInfo(octal_encode, octal_decode, name='syslog-octal')


codecs.register(octal_search)
