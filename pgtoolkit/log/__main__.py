import bdb
import json
import logging
import os
import pdb
import sys
from argparse import ArgumentParser
from distutils.util import strtobool
from typing import List, MutableMapping

from .._helpers import JSONDateEncoder, Timer, open_or_stdin
from .parser import UnknownData, parse

logger = logging.getLogger(__name__)


def main(
    argv: List[str] = sys.argv[1:],
    environ: MutableMapping[str, str] = os.environ,
) -> int:
    debug = strtobool(environ.get("DEBUG", "n"))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname).1s: %(message)s",
    )
    parser = ArgumentParser()
    # Default comes from PostgreSQL documentation.
    parser.add_argument(
        "log_line_prefix",
        default="%m [%p] ",
        metavar="LOG_LINE_PREFIX",
        help="log_line_prefix as configured in PostgreSQL. " "default: '%(default)s'",
    )
    parser.add_argument(
        "filename",
        nargs="?",
        default="-",
        metavar="FILENAME",
        help="Log filename or - for stdin. default: %(default)s",
    )
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
                        print(json.dumps(record.as_dict(), cls=JSONDateEncoder))
        logger.info("Parsed %d records in %s.", counter, timer.delta)
    except (KeyboardInterrupt, bdb.BdbQuit):  # pragma: nocover
        logger.info("Interrupted.")
        return 1
    except Exception:
        logger.exception("Unhandled error:")
        if debug:  # pragma: nocover
            pdb.post_mortem(sys.exc_info()[2])
        return 1
    return 0


if "__main__" == __name__:  # pragma: nocover
    sys.exit(main(argv=sys.argv[1:], environ=os.environ))
