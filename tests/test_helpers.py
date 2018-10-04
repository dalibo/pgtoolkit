from io import StringIO
import pytest


def test_open_or_stdin(mocker):
    from pgtoolkit._helpers import open_or_stdin

    stdin = object()
    assert open_or_stdin('-', stdin=stdin) is stdin

    open_ = mocker.patch(
        'pgtoolkit._helpers.open', creates=True)
    open_.return_value = fo = object()

    assert open_or_stdin('toto.conf') is fo


def test_open_or_return(mocker):
    from pgtoolkit._helpers import open_or_return

    # File case.
    fo = object()
    with open_or_return(fo) as ret:
        assert ret is fo

    # Path case
    open_ = mocker.patch(
        'pgtoolkit._helpers.open', creates=True)
    open_.return_value = fo = StringIO()

    with open_or_return('toto.conf') as ret:
        assert ret is fo

    # None case.
    with pytest.raises(ValueError):
        open_or_return(None)


def test_timer():
    from pgtoolkit._helpers import Timer

    with Timer() as timer:
        pass

    assert timer.start
    assert timer.delta


def test_format_timedelta():
    from datetime import timedelta
    from pgtoolkit._helpers import format_timedelta

    assert '5s' == format_timedelta(timedelta(seconds=5))
    assert '1d 5s' == format_timedelta(timedelta(days=1, seconds=5))
    assert '20us' == format_timedelta(timedelta(microseconds=20))
    assert '0s' == format_timedelta(timedelta())


def test_json_encoder():
    from datetime import datetime, timedelta
    import json
    from pgtoolkit._helpers import JSONDateEncoder

    data_ = dict(
        date=datetime(year=2012, month=12, day=21),
        delta=timedelta(seconds=40),
        integer=42,
    )

    payload = json.dumps(data_, cls=JSONDateEncoder)

    assert '"2012-12-21T00:00:00' in payload
    assert '"40s"' in payload
    assert ': 42' in payload
