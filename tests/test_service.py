from textwrap import dedent
from io import StringIO

import pytest


def test_parse():
    from pgtoolkit.service import parse

    lines = dedent(
        """\
    [service0]
    host=myhost
    port=5432
    user=toto

    [service1]
    host=myhost1
    port=5432
    dbname=myapp
    """
    ).splitlines()

    services = parse(lines, source="in-memory")
    assert 2 == len(services)
    assert "pgtoolkit" not in repr(services)

    service0 = services["service0"]
    assert "service0" == service0.name
    assert "myhost" == service0.host
    assert "service0" in repr(service0)


def test_parse_file(mocker):
    from pgtoolkit.service import parse

    m = mocker.mock_open()
    try:
        mocker.patch("builtins.open", m)
    except Exception:
        mocker.patch("__builtin__.open", m)
    services = parse("filename")

    assert m.called
    services.save()

    m = mocker.Mock()
    try:
        mocker.patch("configparser.ConfigParser.write", new_callable=m)
    except Exception:
        mocker.patch("ConfigParser.ConfigParser.write", new_callable=m)
    assert m.called


def test_render():
    from pgtoolkit.service import Service, ServiceFile

    services = ServiceFile()
    service0 = Service(name="service0", dbname="mydb")
    services.add(service0)

    # Moving options and updating service.
    service0.pop("dbname")
    service0.port = 5432
    services.add(service0)

    service0 = services["service0"]
    assert 5432 == service0.port
    assert "dbname" not in service0

    services.add(Service(name="service1", host="myhost"))

    fo = StringIO()
    services.save(fo)
    raw = fo.getvalue()

    # Ensure no space around =
    assert "host=myhost" in raw


def test_sysconfdir(mocker):
    isdir = mocker.patch("pgtoolkit.service.os.path.isdir", autospec=True)

    from pgtoolkit.service import guess_sysconfdir

    isdir.return_value = False
    with pytest.raises(Exception):
        guess_sysconfdir(environ=dict(PGSYSCONFDIR="/toto"))

    isdir.return_value = True
    sysconfdir = guess_sysconfdir(environ=dict(PGSYSCONFDIR="/toto"))
    assert "/toto" == sysconfdir

    isdir.return_value = False
    with pytest.raises(Exception):
        guess_sysconfdir(environ=dict())

    isdir.return_value = True
    sysconfdir = guess_sysconfdir(environ=dict())
    assert sysconfdir.startswith("/etc")


def test_find(mocker):
    g_scd = mocker.patch("pgtoolkit.service.guess_sysconfdir", autospec=True)
    exists = mocker.patch("pgtoolkit.service.os.path.exists", autospec=True)

    from pgtoolkit.service import find

    exists.return_value = False
    with pytest.raises(Exception):
        find(environ=dict(PGSERVICEFILE="my-services.conf"))

    g_scd.return_value = "/etc/postgresql-common"
    with pytest.raises(Exception):
        find(environ=dict())

    exists.return_value = True
    servicefile = find(environ=dict(PGSERVICEFILE="toto.conf"))
    assert "toto.conf" == servicefile

    exists.side_effect = [False, True]
    servicefile = find(environ=dict())
    assert servicefile.endswith("/pg_service.conf")
    exists.side_effect = None

    g_scd.side_effect = Exception("Pouet")
    servicefile = find(environ=dict())
    assert servicefile.endswith("/.pg_service.conf")
