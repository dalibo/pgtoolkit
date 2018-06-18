def test_open_or_stdin(mocker):
    from pgtoolkit._helpers import open_or_stdin

    stdin = object()
    assert open_or_stdin('-', stdin=stdin) is stdin

    open_ = mocker.patch(
        'pgtoolkit._helpers.open', creates=True)
    open_.return_value = fo = object()

    assert open_or_stdin('toto.conf') is fo


def test_timer():
    from pgtoolkit._helpers import Timer

    with Timer() as timer:
        pass

    assert timer.start
    assert timer.delta
