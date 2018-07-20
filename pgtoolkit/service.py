# coding: utf-8

"""See `The Connection Service File
<https://www.postgresql.org/docs/current/static/libpq-pgservice.html>`__ in
PostgreSQL documentation.


.. autofunction:: pgtoolkit.service.find
.. autofunction:: pgtoolkit.service.parse
.. autoclass:: pgtoolkit.service.Service
.. autoclass:: pgtoolkit.service.ServiceFile


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

from __future__ import print_function

try:
    from configparser import ConfigParser
except ImportError:  # pragma: nocover_py3
    from ConfigParser import ConfigParser

import os
import sys

from ._helpers import open_or_stdin


class Service(dict):
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
    >>> list(myservice.items())
    [('dbname', 'mydb'), ('host', 'myhost'), ('user', 'myuser')]

    """

    def __init__(self, name, parameters=None, **extra):
        super(Service, self).__init__()
        self.name = name
        self.update(parameters or {})
        self.update(extra)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value


class ServiceFile(object):
    """Service file representation, parsing and rendering.

    :class:`ServiceFile` is subscriptable. You can access service using
    ``servicefile['servicename']`` syntax.

    .. automethod:: add
    .. automethod:: parse
    .. automethod:: save
    """

    _CONVERTERS = {
        'port': int,
    }

    def __init__(self):
        self.config = ConfigParser(
            comment_prefixes=('#',),
            delimiters=('=',),
        )

    def __repr__(self):
        return '<%s>' % (self.__class__.__name__)

    def __getitem__(self, key):
        parameters = dict([
            (k, self._CONVERTERS.get(k, str)(v))
            for k, v in self.config.items(key)
        ])
        return Service(key, parameters)

    def __len__(self):
        return len(self.config.sections())

    def add(self, service):
        """Adds a :class:`Service` object to the service file."""
        self.config.remove_section(service.name)
        self.config.add_section(service.name)
        for parameter, value in service.items():
            self.config.set(service.name, parameter, str(value))

    def parse(self, fo, source=None):
        """Add service from a service file.

        This method is strictly the same as :func:`parse`. It’s the method
        counterpart.
        """
        self.config.read_file(fo, source=source)

    def save(self, fo):
        """Writes services in ``fo`` file-like object.

        .. note:: Comments are not preserved.
        """
        self.config.write(fo, space_around_delimiters=False)


def guess_sysconfdir(environ=os.environ):
    fromenv = environ.get('PGSYSCONFDIR')
    if fromenv:
        candidates = [fromenv]
    else:
        candidates = [
            # From PGDG APT packages.
            '/etc/postgresql-common',
            # From PGDG RPM packages.
            '/etc/sysconfig/pgsql',
        ]

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    raise Exception("Can't find sysconfdir")


def find(environ=None):
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

    fromenv = environ.get('PGSERVICEFILE')
    if fromenv:
        candidates = [fromenv]
    else:
        candidates = [os.path.expanduser("~/.pg_service.conf")]
        try:
            sysconfdir = guess_sysconfdir(environ)
        except Exception:
            pass
        else:
            candidates.append(os.path.join(sysconfdir, 'pg_service.conf'))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    raise Exception("Can't find pg_service file.")


def parse(fo, source=None):
    """Parse a service file.

    :param fo: a file-object as returned by open.
    :param source: Name of the source.
    :rtype: A ``ServiceFile`` object.

    Actually it only requires as ``fo`` an iterable object yielding each lines
    of the file. You can provide ``source`` to have more precise error message.

    .. warning::

        pgtoolkit is less strict than `libpq`. `libpq` does not accepts spaces
        around equals.  pgtoolkit accepts them but do not write them.
    """
    services = ServiceFile()
    services.parse(fo, source=source)
    return services


if __name__ == '__main__':  # pragma: nocover
    argv = sys.argv[1:] + ['-']
    try:
        with open_or_stdin(argv[0]) as fo:
            services = parse(fo)
        services.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
