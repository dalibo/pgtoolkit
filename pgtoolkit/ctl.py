"""
.. currentmodule:: pgtoolkit.ctl

API Reference
-------------

.. autoclass:: PGCtl
    :members:
.. autoclass:: Status
    :members:
.. autofunction:: run_command
.. autoclass:: CommandRunner
    :members: __call__
"""

import enum
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Union, TYPE_CHECKING
from typing_extensions import Literal, Protocol

if TYPE_CHECKING:
    CompletedProcess = subprocess.CompletedProcess[str]
else:
    CompletedProcess = subprocess.CompletedProcess

PY37 = sys.version_info[:1] >= (3, 7)


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
    ) -> CompletedProcess:
        ...


def run_command(
    args: Sequence[str],
    *,
    capture_output: bool = False,
    check: bool = False,
    **kwargs: Any,
) -> CompletedProcess:
    """Default :class:`CommandRunner` implementation for :class:`PGCtl` using
    :func:`subprocess.run`.
    """
    if PY37:
        kwargs["capture_output"] = capture_output
    elif capture_output:
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError(
                "stdout and stderr arguments may not be used with capture_output"
            )
        kwargs["stdout"] = kwargs["stderr"] = subprocess.PIPE

    return subprocess.run(
        args,
        check=check,
        universal_newlines=True,
        **kwargs,
    )


def _args_to_opts(args: Mapping[str, Union[str, Literal[True]]]) -> List[str]:
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


def _wait_args_to_opts(wait: Union[bool, int]) -> List[str]:
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


class PGCtl:
    """Handler for pg_ctl commands.

    :param bindir: location of postgresql user executables; if not specified,
        this will be determined by calling ``pg_config`` if that executable is
        found in ``$PATH``.
    :param run_command: callable implementing :class:`CommandRunner` that will
        be used to execute ``pg_ctl`` commands.

    :raises: :class:`EnvironmentError` if either ``pg_config`` or ``pg_ctl``
        is not available.
    """

    def __init__(
        self,
        bindir: Optional[Union[str, Path]] = None,
        *,
        run_command: CommandRunner = run_command,
    ) -> None:
        if bindir is None:
            pg_config = shutil.which("pg_config")
            if pg_config is None:
                raise EnvironmentError("pg_config executable not found")
            bindir = run_command(
                [pg_config, "--bindir"], check=True, capture_output=True
            ).stdout.strip()
        bindir = Path(bindir)
        pg_ctl = bindir / "pg_ctl"
        if not pg_ctl.exists():
            raise EnvironmentError("pg_ctl executable not found")

        self.pg_ctl = pg_ctl
        """Path to ``pg_ctl`` executable."""

        self.run_command = run_command

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
        cmd = [str(self.pg_ctl), "init"] + ["-D", str(datadir)]
        options = _args_to_opts(opts)
        if options:
            cmd.extend(["-o", " ".join(options)])
        return self.run_command(cmd, check=True)

    def start(
        self,
        datadir: Union[Path, str],
        *,
        wait: Union[bool, int] = True,
        logfile: Optional[Union[Path, str]] = None,
    ) -> CompletedProcess:
        """Start a PostgreSQL cluster.

        :param datadir: Path to database storage area
        :param wait: Wait until operation completes, if an integer value is
            passed, this will be used as --timeout value.
        :param logfile: Optional log file path
        """
        cmd = [str(self.pg_ctl), "start"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if logfile:
            cmd.append(f"--log={logfile}")
        return self.run_command(cmd, check=True)

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
        cmd = [str(self.pg_ctl), "stop"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if mode:
            cmd.append(f"--mode={mode}")
        return self.run_command(cmd, check=True)

    def restart(
        self,
        datadir: Union[Path, str],
        *,
        mode: Optional[str] = None,
        wait: Union[bool, int] = True,
    ) -> CompletedProcess:
        """Restart a PostgreSQL cluster.

        :param datadir: Path to database storage area
        :param mode: Shutdown mode, can be "smart", "fast", or "immediate"
        :param wait: Wait until operation completes, if an integer value is
            passed, this will be used as --timeout value.
        """
        cmd = [str(self.pg_ctl), "restart"] + ["-D", str(datadir)]
        cmd.extend(_wait_args_to_opts(wait))
        if mode:
            cmd.append(f"--mode={mode}")
        return self.run_command(cmd, check=True)

    def reload(
        self,
        datadir: Union[Path, str],
    ) -> CompletedProcess:
        """Reload a PostgreSQL cluster.

        :param datadir: Path to database storage area
        """
        cmd = [str(self.pg_ctl), "reload"] + ["-D", str(datadir)]
        return self.run_command(cmd, check=True)

    def status(self, datadir: Union[Path, str]) -> Status:
        """Check PostgreSQL cluster status.

        :param datadir: Path to database storage area
        :return: Status value.
        """
        cmd = [str(self.pg_ctl), "status"] + ["-D", str(datadir)]
        return Status(self.run_command(cmd).returncode)
