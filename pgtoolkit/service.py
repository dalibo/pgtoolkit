""".. currentmodule:: pgtoolkit.service

This module supports reading, validating, editing and rendering ``pg_service``
file. See `The Connection Service File
<https://www.postgresql.org/docs/current/static/libpq-pgservice.html>`__ in
PostgreSQL documentation.

API Reference
-------------

The main entrypoint of the API is the :func:`parse` function. :func:`find`
function may be useful if you need to search for ``pg_service.conf`` files in
regular locations.

.. autofunction:: find
.. autofunction:: parse
.. autoclass:: Service
.. autoclass:: ServiceFile


Edit a service file
-------------------

.. code:: python

    from pgtoolkit.service import parse, Service

    servicefilename = 'my_service.conf'
    with open(servicefile) as fo:
        servicefile = parse(fo, source=servicefilename)

    myservice = servicefile['myservice']
    myservice.host = 'newhost'
    # Update service file
    servicefile.add(myservice)

    newservice = Service(name='newservice', host='otherhost')
    servicefile.add(newservice)

    with open(servicefile, 'w') as fo:
        servicefile.save(fo)

Shorter version using the file directly in `parse`:

.. code:: python

    servicefile = parse('my_service.conf')
    [...]
    servicefile.save()


Load a service file to connect with psycopg2
--------------------------------------------

Actually, psycopg2 already support pgservice file. This is just a showcase.

.. code:: python

    from pgtoolkit.service import find, parse
    from psycopg2 import connect

    servicefilename = find()
    with open(servicefile) as fo:
        servicefile = parse(fo, source=servicefilename)
    connection = connect(**servicefile['myservice'])


Using as a script
-----------------

:mod:`pgtoolkit.service` is usable as a CLI script. It accepts a service file
path as first argument, read it, validate it and re-render it, loosing
comments.

:class:`ServiceFile` is less strict than `libpq`. Spaces are accepted around
`=`. The output conform strictly to `libpq` parser.

.. code:: console

    $ python -m pgtoolkit.service data/pg_service.conf
    [mydb]
    host=somehost
    port=5433
    user=admin

    [my ini-style]
    host=otherhost

"""


from configparser import ConfigParser
import os
import sys
from typing import Dict, IO, Iterable, MutableMapping, Optional, Union

from ._helpers import open_or_stdin


Parameter = Union[str, int]


class Service(Dict[str, Parameter]):
    """Service definition.

    The :class:`Service` class represents a single service definition in a
    Service file. It’s actually a dictionnary of its own parameters.

    The ``name`` attributes is mapped to the section name of the service in the
    Service file.

    Each parameters can be accessed either as a dictionnary entry or as an
    attributes.

    >>> myservice = Service('myservice', {'dbname': 'mydb'}, host='myhost')
    >>> myservice.name
    'myservice'
    >>> myservice.dbname
    'mydb'
    >>> myservice['dbname']
    'mydb'
    >>> myservice.user = 'myuser'
    >>> list(sorted(myservice.items()))
    [('dbname', 'mydb'), ('host', 'myhost'), ('name', 'myservice'), ('user', 'myuser')]

    """  # noqa

    def __init__(
        self,
        name: str,
        parameters: Optional[Dict[str, Parameter]] = None,
        **extra: Parameter,
    ) -> None:
        super(Service, self).__init__()
        self.name = name
        self.update(parameters or {})
        self.update(extra)

    def __repr__(self) -> str:
        return "<%s %s>" % (self.__class__.__name__, self.name)

    def __getattr__(self, name: str) -> Parameter:
        return self[name]

    def __setattr__(self, name: str, value: Parameter) -> None:
        self[name] = value


class ServiceFile:
    """Service file representation, parsing and rendering.

    :class:`ServiceFile` is subscriptable. You can access service using
    ``servicefile['servicename']`` syntax.

    .. automethod:: add
    .. automethod:: parse
    .. automethod:: save

    .. attribute:: path

        Path to a file. Is automatically set when calling :meth:`parse` with a
        path to a file. :meth:`save` will write to this file if set.
    """

    path: Optional[str]

    _CONVERTERS = {
        "port": int,
    }

    def __init__(self) -> None:
        self.path = None
        self.config = ConfigParser(
            comment_prefixes=("#",),
            delimiters=("=",),
        )

    def __repr__(self) -> str:
        return "<%s>" % (self.__class__.__name__)

    def __getitem__(self, key: str) -> Service:
        parameters = dict(
            [(k, self._CONVERTERS.get(k, str)(v)) for k, v in self.config.items(key)]
        )
        return Service(key, parameters)

    def __len__(self) -> int:
        return len(self.config.sections())

    def add(self, service: Service) -> None:
        """Adds a :class:`Service` object to the service file."""
        self.config.remove_section(service.name)
        self.config.add_section(service.name)
        for parameter, value in service.items():
            self.config.set(service.name, parameter, str(value))

    def parse(self, fo: Iterable[str], source: Optional[str] = None) -> None:
        """Add service from a service file.

        This method is strictly the same as :func:`parse`. It’s the method
        counterpart.
        """
        self.config.read_file(fo, source=source)

    def save(self, fo: Optional[IO[str]] = None) -> None:
        """Writes services in ``fo`` file-like object.

        :param fo: a file-like object. Is not required if :attr:`path` is set.

        .. note:: Comments are not preserved.
        """
        config = self.config

        def _write(fo: IO[str]) -> None:
            config.write(fo, space_around_delimiters=False)

        if fo:
            _write(fo)
        elif self.path:
            with open(self.path, "w") as fo:
                _write(fo)
        else:
            raise ValueError("No file-like object nor path provided")


def guess_sysconfdir(environ: MutableMapping[str, str] = os.environ) -> str:
    fromenv = environ.get("PGSYSCONFDIR")
    if fromenv:
        candidates = [fromenv]
    else:
        candidates = [
            # From PGDG APT packages.
            "/etc/postgresql-common",
            # From PGDG RPM packages.
            "/etc/sysconfig/pgsql",
        ]

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    raise Exception("Can't find sysconfdir")


def find(environ: Optional[MutableMapping[str, str]] = None) -> str:
    """Find service file.

    :param dict environ: Dict of environment variables.

    :func:`find` searches for the first candidate of ``pg_service.conf`` file
    from either environment and regular locations. :func:`find` raises an
    Exception if it fails to find a Connection service file.

    .. code:: python

        from pgtoolkit.service import find

        try:
            servicefile = find()
        except Exception as e:
            "Deal with exception."
        else:
            "Manage servicefile."

    """
    if environ is None:
        environ = os.environ

    fromenv = environ.get("PGSERVICEFILE")
    if fromenv:
        candidates = [fromenv]
    else:
        candidates = [os.path.expanduser("~/.pg_service.conf")]
        try:
            sysconfdir = guess_sysconfdir(environ)
        except Exception:
            pass
        else:
            candidates.append(os.path.join(sysconfdir, "pg_service.conf"))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    raise Exception("Can't find pg_service file.")


def parse(file: Union[str, Iterable[str]], source: Optional[str] = None) -> ServiceFile:
    """Parse a service file.

    :param file: a file-object as returned by open or a string corresponding to
        the path to a file to open and parse.
    :param source: Name of the source.
    :rtype: A ``ServiceFile`` object.

    Actually it only requires as ``fo`` an iterable object yielding each lines
    of the file. You can provide ``source`` to have more precise error message.

    .. warning::

        pgtoolkit is less strict than `libpq`. `libpq` does not accepts spaces
        around equals. pgtoolkit accepts spaces but do not write them.

    """
    if isinstance(file, str):
        with open(file) as fo:
            services = parse(fo, source=source)
            services.path = file
    else:
        services = ServiceFile()
        services.parse(file, source=source)
    return services


if __name__ == "__main__":  # pragma: nocover
    argv = sys.argv[1:] + ["-"]
    try:
        with open_or_stdin(argv[0]) as fo:
            services = parse(fo)
        services.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
