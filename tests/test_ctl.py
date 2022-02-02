import shlex
import socket
import stat
import subprocess

import pytest

from pgtoolkit import ctl, hba


def test__args_to_opts():
    opts = ctl._args_to_opts(
        {
            "encoding": "latin1",
            "auth_local": "trust",
            "show": True,
            "n": True,
            "L": "DIR",
        }
    )
    assert opts == [
        "-L DIR",
        "--auth-local=trust",
        "--encoding=latin1",
        "-n",
        "--show",
    ]


def test__wait_args_to_opts():
    assert ctl._wait_args_to_opts(False) == ["--no-wait"]
    assert ctl._wait_args_to_opts(True) == ["--wait"]
    assert ctl._wait_args_to_opts(42) == ["--wait", "--timeout=42"]


@pytest.fixture
def fake_pgctl(tmp_path):
    (tmp_path / "pg_ctl").touch(mode=0o777)
    with open(tmp_path / "pg_ctl", "w") as f:
        f.write("#!/bin/sh\necho 'pg_ctl (PostgreSQL) 11.10'")
    c = ctl.PGCtl(tmp_path)

    def run_command(args, **kwargs):
        return subprocess.CompletedProcess(
            " ".join(shlex.quote(a) for a in args), c.code
        )

    c.code = 0
    c.run_command = run_command
    c.pg_ctl = "pg_ctl"
    return c


def test_init(fake_pgctl):
    r = fake_pgctl.init(
        "data",
        auth_local="md5",
        data_checksums=True,
        g=True,
        X="wal",
    )
    assert r.args == (
        "pg_ctl init -D data -o '-X wal --auth-local=md5 --data-checksums -g'"
    )


def test_start(fake_pgctl):
    assert fake_pgctl.start("data").args == "pg_ctl start -D data --wait"
    assert fake_pgctl.start("data", wait=False).args == "pg_ctl start -D data --no-wait"
    assert fake_pgctl.start(
        "data",
        wait=3,
        logfile="logfile",
    ).args == ("pg_ctl start -D data --wait --timeout=3 --log=logfile")
    assert fake_pgctl.start("data", k="/tmp/sockets").args == (
        "pg_ctl start -D data --wait -o '-k /tmp/sockets'"
    )


def test_stop(fake_pgctl):
    assert fake_pgctl.stop("data").args == "pg_ctl stop -D data --wait"
    assert fake_pgctl.stop("data", wait=False).args == "pg_ctl stop -D data --no-wait"
    assert fake_pgctl.stop(
        "data",
        wait=3,
        mode="fast",
    ).args == ("pg_ctl stop -D data --wait --timeout=3 --mode=fast")


def test_restart(fake_pgctl):
    assert fake_pgctl.restart("data").args == "pg_ctl restart -D data --wait"
    assert (
        fake_pgctl.restart("data", wait=False).args
        == "pg_ctl restart -D data --no-wait"
    )
    assert (
        fake_pgctl.restart(
            "data",
            wait=3,
            mode="fast",
        ).args
        == "pg_ctl restart -D data --wait --timeout=3 --mode=fast"
    )
    assert fake_pgctl.restart("data", k="/tmp/sockets").args == (
        "pg_ctl restart -D data --wait -o '-k /tmp/sockets'"
    )


def test_reload(fake_pgctl):
    assert fake_pgctl.reload("data").args == "pg_ctl reload -D data"


def test_status(fake_pgctl):
    assert fake_pgctl.status("data") == ctl.Status.running
    fake_pgctl.code = 3
    assert fake_pgctl.status("data") == ctl.Status.not_running
    fake_pgctl.code = 4
    assert fake_pgctl.status("data") == ctl.Status.unspecified_datadir
    fake_pgctl.code = 1
    with pytest.raises(subprocess.CalledProcessError):
        fake_pgctl.status("data")


@pytest.fixture(scope="module")
def pg_ctl():
    try:
        return ctl.PGCtl()
    except EnvironmentError as e:
        pytest.skip(str(e))


def test_func_pgctl(pg_ctl):
    assert pg_ctl.pg_ctl


@pytest.fixture(scope="module")
def initdb(tmp_path_factory, pg_ctl):
    datadir = tmp_path_factory.mktemp("data")
    waldir = tmp_path_factory.mktemp("wal")
    pg_ctl.init(
        datadir,
        auth_local="scram-sha-256",
        data_checksums=True,
        g=True,
        X=waldir,
    )
    run_path = tmp_path_factory.mktemp("run")
    pid_path = run_path / "pid"
    with (datadir / "postgresql.conf").open("a") as f:
        f.write(f"\nunix_socket_directories = '{run_path}'")
        f.write(f"\nexternal_pid_file = '{pid_path}'")
    yield datadir, waldir, pid_path


def test_func_init(initdb):
    datadir, waldir, __ = initdb
    assert (datadir / "PG_VERSION").exists()
    assert (waldir / "archive_status").is_dir()
    with (datadir / "pg_hba.conf").open() as f:
        pghba = hba.parse(f)
    assert next(iter(pghba)).method == "scram-sha-256"
    st_mode = datadir.stat().st_mode
    assert st_mode & stat.S_IRGRP
    assert st_mode & stat.S_IXGRP
    assert not st_mode & stat.S_IWGRP


@pytest.fixture
def tmp_port():
    s = socket.socket()
    s.bind(("", 0))
    with s:
        port = s.getsockname()[1]
    return port


def test_func_start_stop_status_restart_reload(initdb, pg_ctl, tmp_port):
    from psycopg2 import connect

    datadir, __, pidpath = initdb
    assert pg_ctl.status("invalid") == ctl.Status.unspecified_datadir
    assert pg_ctl.status(str(datadir)) == ctl.Status.not_running
    assert not pidpath.exists()
    pg_ctl.start(str(datadir), logfile=datadir / "logs", port=str(tmp_port))
    assert pidpath.exists()
    pid1 = pidpath.read_text()

    connection = connect(dbname="postgres", host="0.0.0.0", port=tmp_port)
    assert connection.info.server_version == pg_ctl.version

    assert pg_ctl.status(str(datadir)) == ctl.Status.running
    pg_ctl.restart(str(datadir), mode="immediate", wait=2)
    pid2 = pidpath.read_text()
    assert pid2 != pid1
    assert pg_ctl.status(str(datadir)) == ctl.Status.running
    pg_ctl.reload(str(datadir))
    pid3 = pidpath.read_text()
    assert pid3 == pid2
    assert pg_ctl.status(str(datadir)) == ctl.Status.running
    pg_ctl.stop(str(datadir), mode="smart")
    assert not pidpath.exists()
    assert pg_ctl.status(str(datadir)) == ctl.Status.not_running


def test_unit__parse_controldata(pg_ctl):
    lines = [
        "pg_control version number:            1100",
        "Catalog version number:               201809051",
        "Database system identifier:           6798427594087098476",
        "Database cluster state:               shut down",
        "pg_control last modified:             Tue 07 Jul 2020 01:08:58 PM CEST",
        "WAL block size:                       8192",
    ]
    controldata = pg_ctl._parse_control_data(lines)
    assert controldata == {
        "Catalog version number": "201809051",
        "Database cluster state": "shut down",
        "Database system identifier": "6798427594087098476",
        "WAL block size": "8192",
        "pg_control last modified": "Tue 07 Jul 2020 01:08:58 PM CEST",
        "pg_control version number": "1100",
    }


def test_func_controldata(initdb, pg_ctl):
    datadir, __, __ = initdb
    controldata = pg_ctl.controldata(datadir=datadir)
    assert "Database block size" in controldata
    assert controldata["Database block size"] == "8192"
    assert "Database cluster state" in controldata
