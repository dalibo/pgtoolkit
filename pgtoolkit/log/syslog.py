# coding: utf-8
import codecs
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
                # Avoid codecs registry and use impl directly.
                message, _ = octal_decode(message)
                line = SyslogLine(message, **m.groupdict())
            yield line


class SyslogLine(str):
    def __new__(cls, message, **kw):
        # str.__init__ signature is fixed. Let's use __new__.
        self = super(SyslogLine, cls).__new__(cls, message)
        self.__dict__.update(kw)
        return self


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
