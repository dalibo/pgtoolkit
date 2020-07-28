from datetime import timedelta
from textwrap import dedent
from io import StringIO

import pytest


def test_parse_value():
    from pgtoolkit.conf import parse_value

    # Booleans
    assert parse_value('on') is True
    assert parse_value('off') is False
    assert parse_value('true') is True
    assert parse_value('false') is False
    assert parse_value('yes') is True
    assert parse_value("'no'") is False

    # Numbers
    assert 10 == parse_value('10')
    assert 8 == parse_value('010')
    assert 8 == parse_value("'010'")
    assert 1.4 == parse_value('1.4')
    assert -2 == parse_value('-2')

    # Strings
    assert '/a/path/to/file.conf' == parse_value(r"/a/path/to/file.conf")
    assert '0755.log' == parse_value(r"0755.log")
    assert 'file_ending_with_B' == parse_value(r"file_ending_with_B")
    assert 'esc\'aped string' == parse_value(r"'esc\'aped string'")
    assert '%m [%p] %q%u@%d ' == parse_value(r"'%m [%p] %q%u@%d '")
    assert '124.7MB' == parse_value("124.7MB")
    assert '124.7ms' == parse_value("124.7ms")

    # Memory
    assert 1024 == parse_value('1kB')
    assert 1024 * 1024 * 512 == parse_value('512MB')
    assert 1024 * 1024 * 1024 * 64 == parse_value(' 64 GB ')
    assert 1024 * 1024 * 1024 * 1024 * 5 == parse_value('5TB')

    # Time
    delta = parse_value('150 ms')
    assert 150000 == delta.microseconds
    delta = parse_value('24s ')
    assert 24 == delta.seconds
    delta = parse_value("' 5 min'")
    assert 300 == delta.seconds
    delta = parse_value('2 h')
    assert 7200 == delta.seconds
    delta = parse_value('5d')
    assert 5 == delta.days

    # Enums
    assert 'md5' == parse_value('md5')

    # Errors
    with pytest.raises(ValueError):
        parse_value("'missing last quote")


def test_parser():
    from pgtoolkit.conf import parse

    lines = dedent("""\
    # - Connection Settings -
    listen_addresses = '*'                  # comma-separated list of addresses;
                            # defaults to 'localhost'; use '*' for all
                            # (change requires restart)

    port = 5432
    bonjour 'without equals'
    shared.buffers = 248MB
    """).splitlines(True)  # noqa

    conf = parse(lines)

    assert '*' == conf.listen_addresses
    assert 5432 == conf.port
    assert 'without equals' == conf.bonjour
    assert 248 * 1024 * 1024 == conf['shared.buffers']

    dict_ = conf.as_dict()
    assert '*' == dict_['listen_addresses']

    with pytest.raises(AttributeError):
        conf.inexistant

    with pytest.raises(KeyError):
        conf['inexistant']

    with pytest.raises(ValueError):
        parse(['bad_line'])


def test_serialize_entry():
    from pgtoolkit.conf import Entry

    e = Entry(name='grp.setting', value=True)

    assert 'grp.setting' in repr(e)
    assert 'grp.setting = true' == str(e)

    assert "'2 kB'" == Entry(name='var', value=2048).serialize()
    assert 'var = 15' == str(Entry(name='var', value=15))
    assert 'var = 0.1' == str(Entry(name='var', value=.1))
    assert 'var = enum' == str(Entry(name='var', value='enum'))
    assert "var = 'sp ced'" == str(Entry(name='var', value='sp ced'))
    assert r"var = 'quo\'ed'" == str(Entry(name='var', value="quo'ed"))

    assert "'1d'" == Entry('var', value=timedelta(days=1)).serialize()
    assert "'1h'" == Entry('var', value=timedelta(minutes=60)).serialize()
    assert "'61 min'" == Entry('var', value=timedelta(minutes=61)).serialize()
    e = Entry('var', value=timedelta(microseconds=12000))
    assert "'12 ms'" == e.serialize()

    assert '  # Comment' in str(Entry('var', 1, comment='Comment'))


def test_save():
    from pgtoolkit.conf import parse

    conf = parse(['listen_addresses = *'])
    fo = StringIO()
    conf.save(fo)
    out = fo.getvalue()
    assert 'listen_addresses = *' in out


def test_edit():
    from pgtoolkit.conf import Configuration

    conf = Configuration()

    conf.listen_addresses = '*'
    assert '*' == conf.listen_addresses

    conf['port'] = 5432
    assert 5432 == conf.port

    conf['port'] = 5433
    assert 5433 == conf.port

    with StringIO() as fo:
        conf.save(fo)
        out = fo.getvalue()

    assert 'port = 5433' in out
