"""
.. currentmodule:: pgtoolkit.ctl

API Reference
-------------

.. autoclass:: PGCtl
    :members:
.. autoclass:: AsyncPGCtl
    :members:
.. autoclass:: Status
    :members:
.. autofunction:: run_command
.. autofunction:: asyncio_run_command
.. autoclass:: CommandRunner
    :members: __call__
.. autoclass:: AsyncCommandRunner
    :members: __call__
"""

import abc
import asyncio
import enum
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional, Protocol, Union

if TYPE_CHECKING:
    CompletedProcess = subprocess.CompletedProcess[str]
else:
    CompletedProcess = subprocess.CompletedProcess


class CommandRunner(Protocol):
    """Protocol for `run_command` callable parameter of :class:`PGCtl`.

    The `text` mode, as defined in :mod:`subprocess`, must be used in
    implementations.

    Keyword arguments are expected to match that of :func:`subprocess.run`.
    """

    def __call__(
        self,
        args: Sequence[str],
        *,
        capture_output: bool = False,
        check: bool = False,
        **kwargs: Any,
    ) -> CompletedProcess: ...


class AsyncCommandRunner(Protocol):
    """Protocol for `run_command` callable parameter of :class:`PGCtl`.

    The `text` mode, as defined in :mod:`subprocess`, must be used in
    implementations.

    Keyword arguments are expected to match that of :func:`subprocess.run`.
    """

    async def __call__(
        self,
        args: Sequence[str],
        *,
        capture_output: bool = False,
        check: bool = False,
        **kwargs: Any,
    ) -> CompletedProcess: ...


def run_command(
    args: Sequence[str],
    *,
    check: bool = False,
    **kwargs: Any,
) -> CompletedProcess:
    """Default :class:`CommandRunner` implementation for :class:`PGCtl` using
    :func:`subprocess.run`.
    """
    return subprocess.run(
        args,
        check=check,
        universal_newlines=True,
        **kwargs,
    )


async def asyncio_run_command(
    args: Sequence[str],
    *,
    capture_output: bool = False,
    check: bool = False,
    **kwargs: Any,
) -> CompletedProcess:
    """Default :class:`AsyncCommandRunner` implementation for
    :class:`AsyncPGCtl` using :func:`asyncio.subprocess`.
    """
    if capture_output:
        kwargs["stdout"] = kwargs["stderr"] = subprocess.PIPE
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    stdout, stderr = await proc.communicate()
    assert proc.returncode is not None
    r = CompletedProcess(
        args,
        proc.returncode,
        stdout.decode() if stdout is not None else None,
        stderr.decode() if stderr is not None else None,
    )
    if check:
        r.check_returncode()
    return r


def _args_to_opts(args: Mapping[str, Union[str, Literal[True]]]) -> list[str]:
    options = []
    for name, value in sorted(args.items()):
        short = len(name) == 1
        name = name.replace("_", "-")
        if value is True:
            opt = f"-{name}" if short else f"--{name}"
        else:
            opt = f"-{name} {value}" if short else f"--{name}={value}"
        options.append(opt)
    return options


def _wait_args_to_opts(wait: Union[bool, int]) -> list[str]:
    options = []
    if not wait:
        options.append("--no-wait")
    else:
        options.append("--wait")
        if isinstance(wait, int) and not isinstance(wait, bool):
            options.append(f"--timeout={wait}")
    return options


@enum.unique
class Status(enum.IntEnum):
    """PostgreSQL cluster runtime status."""

    running = 0
    """Running"""
    not_running = 3
    """Not running"""
    unspecified_datadir = 4
    """Unspecified data directory"""


class AbstractPGCtl(abc.ABC):
    bindir: Path
    version: int

    @cached_property
    def pg_ctl(self) -> Path:
        """Path to ``pg_ctl`` executable."""
        value = self.bindir / "pg_ctl"
        if not value.exists():
            raise OSError("pg_ctl executable not found")
        return value

    def version_cmd(self) -> list[str]:
        return [str(self.pg_ctl), "--version"]

    def init_cmd(
        self, datadir: Union[Path, str], **opts: Union[str, Literal[True]]
    ) -> list[str]:
        cmd = [str(self.pg_ctl), "init"] + ["-D", str(datadir)]
        options = _args_to_opts(opts)
        if options:
            cmd.extend(["-o", " ".join(options)])
        return cmd

    def start_cmd(
        self,
        datadir: Union[Path, str],
        *,
        wait: Union[bool, int] = True,
        logfile: Optional[Union[Path, str]] = None,
        **opts: Union[str, Literal[True]],
    ) -> list[str]:
        cmd = [str(self.pg_ctl), "start"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if logfile:
            cmd.append(f"--log={logfile}")
        options = _args_to_opts(opts)
        if options:
            cmd.extend(["-o", " ".join(options)])
        return cmd

    def stop_cmd(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
    ) -> list[str]:
        cmd = [str(self.pg_ctl), "stop"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if mode:
            cmd.append(f"--mode={mode}")
        return cmd

    def restart_cmd(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
        **opts: Union[str, Literal[True]],
    ) -> list[str]:
        cmd = [str(self.pg_ctl), "restart"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if mode:
            cmd.append(f"--mode={mode}")
        options = _args_to_opts(opts)
        if options:
            cmd.extend(["-o", " ".join(options)])
        return cmd

    def reload_cmd(self, datadir: Union[Path, str]) -> list[str]:
        return [str(self.pg_ctl), "reload"] + ["-D", str(datadir)]

    def status_cmd(self, datadir: Union[Path, str]) -> list[str]:
        return [str(self.pg_ctl), "status"] + ["-D", str(datadir)]

    def controldata_cmd(self, datadir: Union[Path, str]) -> list[str]:
        pg_controldata = self.bindir / "pg_controldata"
        if not pg_controldata.exists():
            raise OSError("pg_controldata executable not found")
        return [str(pg_controldata)] + ["-D", str(datadir)]

    def _parse_control_data(self, lines: list[str]) -> dict[str, str]:
        """Parse pg_controldata command output."""
        controldata = {}
        for line in lines:
            m = re.match(r"^([^:]+):(.*)$", line)
            if m:
                controldata[m.group(1).strip()] = m.group(2).strip()
        return controldata


class PGCtl(AbstractPGCtl):
    """Handler for pg_ctl commands.

    :param bindir: location of postgresql user executables; if not specified,
        this will be determined by calling ``pg_config`` if that executable is
        found in ``$PATH``.
    :param run_command: callable implementing :class:`CommandRunner` that will
        be used to execute ``pg_ctl`` commands.

    :raises: :class:`OSError` if either ``pg_config`` or ``pg_ctl``
        is not available.
    """

    run_command: CommandRunner

    def __init__(
        self,
        bindir: Optional[Union[str, Path]] = None,
        *,
        run_command: CommandRunner = run_command,
    ) -> None:
        if bindir is None:
            pg_config = shutil.which("pg_config")
            if pg_config is None:
                raise OSError("pg_config executable not found")
            bindir = run_command(
                [pg_config, "--bindir"], check=True, capture_output=True
            ).stdout.strip()
        self.bindir = Path(bindir)
        self.run_command = run_command
        version = run_command(
            self.version_cmd(), check=True, capture_output=True
        ).stdout.strip()
        self.version = num_version(version)

    def init(
        self, datadir: Union[Path, str], **opts: Union[str, Literal[True]]
    ) -> CompletedProcess:
        """Initialize a PostgreSQL cluster (initdb) at `datadir`.

        :param datadir: Path to database storage area
        :param opts: extra options passed to initdb

        Options name passed as `opts` should be underscore'd instead dash'ed
        and flag options should be passed a boolean ``True`` value; e.g.
        ``auth_local="md5", data_checksums=True`` for ``pg_ctl init -o
        '--auth-local=md5 --data-checksums'``.
        """
        return self.run_command(self.init_cmd(datadir, **opts), check=True)

    def start(
        self,
        datadir: Union[Path, str],
        *,
        wait: Union[bool, int] = True,
        logfile: Optional[Union[Path, str]] = None,
        **opts: Union[str, Literal[True]],
    ) -> CompletedProcess:
        """Start a PostgreSQL cluster.

        :param datadir: Path to database storage area
        :param wait: Wait until operation completes, if an integer value is
            passed, this will be used as --timeout value.
        :param logfile: Optional log file path
        :param opts: extra options passed to ``postgres`` command.

        Options name passed as `opts` should be underscore'd instead of dash'ed
        and flag options should be passed a boolean ``True`` value; e.g.
        ``F=True, work_mem=123`` for ``pg_ctl start -o '-F --work-mem=123'``.
        """
        return self.run_command(
            self.start_cmd(datadir, wait=wait, logfile=logfile, **opts), check=True
        )

    def stop(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
    ) -> CompletedProcess:
        """Stop a PostgreSQL cluster.

        :param datadir: Path to database storage area
        :param mode: Shutdown mode, can be "smart", "fast", or "immediate"
        :param wait: Wait until operation completes, if an integer value is
            passed, this will be used as --timeout value.
        """
        return self.run_command(
            self.stop_cmd(datadir, mode=mode, wait=wait), check=True
        )

    def restart(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
        **opts: Union[str, Literal[True]],
    ) -> CompletedProcess:
        """Restart a PostgreSQL cluster.

        :param datadir: Path to database storage area
        :param mode: Shutdown mode, can be "smart", "fast", or "immediate"
        :param wait: Wait until operation completes, if an integer value is
            passed, this will be used as --timeout value.
        :param opts: extra options passed to ``postgres`` command.

        Options name passed as `opts` should be underscore'd instead of dash'ed
        and flag options should be passed a boolean ``True`` value; e.g.
        ``F=True, work_mem=123`` for ``pg_ctl restart -o '-F --work-mem=123'``.
        """
        return self.run_command(
            self.restart_cmd(datadir, mode=mode, wait=wait, **opts), check=True
        )

    def reload(
        self,
        datadir: Union[Path, str],
    ) -> CompletedProcess:
        """Reload a PostgreSQL cluster.

        :param datadir: Path to database storage area
        """
        return self.run_command(self.reload_cmd(datadir), check=True)

    def status(self, datadir: Union[Path, str]) -> Status:
        """Check PostgreSQL cluster status.

        :param datadir: Path to database storage area
        :return: Status value.
        """
        cp = self.run_command(self.status_cmd(datadir))
        rc = cp.returncode
        if rc == 1:
            raise subprocess.CalledProcessError(rc, cp.args, cp.stdout, cp.stderr)
        return Status(rc)

    def controldata(self, datadir: Union[Path, str]) -> dict[str, str]:
        """Run the pg_controldata command and parse the result to return
        controldata as dict.

        :param datadir: Path to database storage area
        """
        r = self.run_command(
            self.controldata_cmd(datadir),
            check=True,
            env={"LC_ALL": "C"},
            capture_output=True,
        ).stdout
        return parse_control_data(r.splitlines())


class AsyncPGCtl(AbstractPGCtl):
    """Async handler for pg_ctl commands.

    See :class:`PGCtl` for the interface.
    """

    run_command: AsyncCommandRunner

    def __init__(self, bindir: Path, run_command: AsyncCommandRunner) -> None:
        self.bindir = bindir
        self.run_command = run_command

    @classmethod
    async def get(
        cls,
        bindir: Optional[Union[str, Path]] = None,
        *,
        run_command: AsyncCommandRunner = asyncio_run_command,
    ) -> "AsyncPGCtl":
        """Construct an AsyncPGCtl instance from specified or inferred 'bindir'.

        :param bindir: location of postgresql user executables; if not specified,
            this will be determined by calling ``pg_config`` if that executable is
            found in ``$PATH``.
        :param run_command: callable implementing :class:`CommandRunner` that will
            be used to execute ``pg_ctl`` commands.

        :raises: :class:`OSError` if either ``pg_config`` or ``pg_ctl``
            is not available.
        """
        if bindir is None:
            pg_config = shutil.which("pg_config")
            if pg_config is None:
                raise OSError("pg_config executable not found")
            bindir = (
                await run_command(
                    [pg_config, "--bindir"], check=True, capture_output=True
                )
            ).stdout.strip()
        bindir = Path(bindir)
        self = cls(bindir, run_command)
        version = (
            await run_command(self.version_cmd(), check=True, capture_output=True)
        ).stdout.strip()
        self.version = num_version(version)
        return self

    async def init(
        self, datadir: Union[Path, str], **opts: Union[str, Literal[True]]
    ) -> CompletedProcess:
        return await self.run_command(self.init_cmd(datadir, **opts), check=True)

    async def start(
        self,
        datadir: Union[Path, str],
        *,
        wait: Union[bool, int] = True,
        logfile: Optional[Union[Path, str]] = None,
        **opts: Union[str, Literal[True]],
    ) -> CompletedProcess:
        return await self.run_command(
            self.start_cmd(datadir, wait=wait, logfile=logfile, **opts), check=True
        )

    async def stop(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
    ) -> CompletedProcess:
        return await self.run_command(
            self.stop_cmd(datadir, mode=mode, wait=wait), check=True
        )

    async def restart(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
        **opts: Union[str, Literal[True]],
    ) -> CompletedProcess:
        return await self.run_command(
            self.restart_cmd(datadir, mode=mode, wait=wait, **opts), check=True
        )

    async def reload(
        self,
        datadir: Union[Path, str],
    ) -> CompletedProcess:
        return await self.run_command(self.reload_cmd(datadir), check=True)

    async def status(self, datadir: Union[Path, str]) -> Status:
        cp = await self.run_command(self.status_cmd(datadir))
        rc = cp.returncode
        if rc == 1:
            raise subprocess.CalledProcessError(rc, cp.args, cp.stdout, cp.stderr)
        return Status(rc)

    async def controldata(self, datadir: Union[Path, str]) -> dict[str, str]:
        r = (
            await self.run_command(
                self.controldata_cmd(datadir),
                check=True,
                env={"LC_ALL": "C"},
                capture_output=True,
            )
        ).stdout
        return parse_control_data(r.splitlines())


def parse_control_data(lines: Sequence[str]) -> dict[str, str]:
    """Parse pg_controldata command output."""
    controldata = {}
    for line in lines:
        m = re.match(r"^([^:]+):(.*)$", line)
        if m:
            controldata[m.group(1).strip()] = m.group(2).strip()
    return controldata


def num_version(text_version: str) -> int:
    """Return PostgreSQL numeric version as defined by LibPQ PQserverVersion

    >>> num_version('pg_ctl (PostgreSQL) 9.6.3')
    90603
    >>> num_version('pg_ctl (PostgreSQL) 9.2.0')
    90200
    >>> num_version('pg_ctl (PostgreSQL) 11.10')
    110010
    >>> num_version('pg_ctl (PostgreSQL) 11.1')
    110001
    >>> num_version("pg_ctl (PostgreSQL) 14devel")
    140000
    >>> num_version("pg_ctl (PostgreSQL) 9.6devel")
    90600
    >>> num_version("pg_ctl (PostgreSQL) 9.6rc1")
    90600
    """
    res = re.match(
        r"pg_ctl \(\w+\) ([0-9]+)\.([0-9]+)(?:\.([0-9]+))?",
        text_version,
    )
    if res is not None:
        rmatch = res.group(1)
        if int(res.group(1)) < 10:
            rmatch += res.group(2).rjust(2, "0")
            if res.group(3) is not None:
                rmatch += res.group(3).rjust(2, "0")
            else:
                return num_dev_version(text_version)
        else:
            rmatch += res.group(2).rjust(4, "0")
        pg_num_version = int(rmatch)
        return pg_num_version
    return num_dev_version(text_version)


def num_dev_version(text_version: str) -> int:
    """Return PostgreSQL numeric version as defined by LibPQ PQserverVersion

    >>> num_dev_version("pg_ctl (PostgreSQL) 14devel")
    140000
    >>> num_dev_version("pg_ctl (PostgreSQL) 13beta1")
    130000
    >>> num_dev_version("pg_ctl (PostgreSQL) 13rc1")
    130000
    >>> num_dev_version("pg_ctl (PostgreSQL) 9.6devel")
    90600
    """
    res = re.match(
        r"pg_ctl \(\w+\) ([0-9]+)(?:\.([0-9]+))?(devel|beta[0-9]+|rc[0-9]+)",
        text_version,
    )
    if not res:
        raise Exception(f"Undefined PostgreSQL version: {text_version}")
    rmatch = res.group(1)
    if res.group(2) is not None:
        rmatch += res.group(2).rjust(2, "0") + "00"
    else:
        rmatch += "0000"
    pg_num_version = int(rmatch)
    return pg_num_version
