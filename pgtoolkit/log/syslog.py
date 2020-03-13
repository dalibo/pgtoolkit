import re


class SyslogPreprocessor(object):
    def __init__(self, syslog_sequence_numbers=True):
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
        for line in lines:
            m = self._re.match(line)
            if m:
                message = line[len(m.group(0)):]
                line = SyslogLine(message, **m.groupdict())
            yield line


class SyslogLine(str):
    def __new__(cls, message, **kw):
        # str.__init__ signature is fixed. Let's use __new__.
        self = super(SyslogLine, cls).__new__(cls, message)
        self.__dict__.update(kw)
        return self
