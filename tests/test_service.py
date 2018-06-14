from textwrap import dedent
from io import StringIO

import pytest


def test_parse():
    from pgtoolkit.service import parse

    lines = dedent("""\
    [service0]
    host=myhost
    port=5432
    user=toto

    [service1]
    host=myhost1
    port=5432
    dbname=myapp
    """).splitlines()

    services = parse(lines, source='in-memory')
    assert 2 == len(services)
    assert 'pgtoolkit' not in repr(services)

    service0 = services['service0']
    assert 'service0' == service0.name
    assert 'myhost' == service0.host
    assert 'service0' in repr(service0)


def test_render():
    from pgtoolkit.service import Service, ServiceFile

    services = ServiceFile()
    service0 = Service(name='service0', dbname='mydb')
    services.add(service0)

    # Moving options and updating service.
    service0.pop('dbname')
    service0.port = 5432
    services.add(service0)

    service0 = services['service0']
    assert 5432 == service0.port
    assert 'dbname' not in service0

    services.add(Service(name='service1', host='myhost'))

    fo = StringIO()
    services.save(fo)
    raw = fo.getvalue()

    # Ensure no space around =
    assert 'host=myhost' in raw
