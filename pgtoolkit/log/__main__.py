from __future__ import print_function

import json
import logging
import os
import sys
from argparse import ArgumentParser

from .._helpers import JSONDateEncoder
from .._helpers import open_or_stdin
from .._helpers import Timer
from . import parse, UnknownData


logger = logging.getLogger(__name__)


def main(argv=sys.argv[1:], environ=os.environ):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)5.5s %(message)s',
    )
    parser = ArgumentParser()
    # Default comes from PostgreSQL documentation.
    parser.add_argument(
        "log_line_prefix", default="%m [%p] ",
        metavar="LOG_LINE_PREFIX",
        help="log_line_prefix as configured in PostgreSQL. "
        "default: '%(default)s'")
    parser.add_argument(
        "filename", nargs="?", default="-", metavar="FILENAME",
        help="Log filename or - for stdin. default: %(default)s")
    args = parser.parse_args(argv)

    counter = 0
    try:
        with open_or_stdin(args.filename) as fo:
            with Timer() as timer:
                for record in parse(fo, prefix_fmt=args.log_line_prefix):
                    if isinstance(record, UnknownData):
                        logger.warning("%s", record)
                    else:
                        counter += 1
                        print(
                            json.dumps(record.as_dict(), cls=JSONDateEncoder))
        logger.info("Parsed %d records in %s.", counter, timer.delta)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if '__main__' == __name__:  # pragma: nocover
    sys.exit(main(argv=sys.argv[1:], environ=os.environ))