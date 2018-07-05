# coding: utf-8

"""
========================
:mod:`pgtoolkit.service`
========================

See `The Connection Service File
<https://www.postgresql.org/docs/current/static/libpq-pgservice.html>`__ in
PostgreSQL documentation.


.. autofunction:: pgtoolkit.service.parse

class ``pgtoolkit.service.Service(name, parameters, **extra)``
--------------------------------------------------------------

The ``Service`` class represent a single service definition in a Service
file. It’s actually a dictionnary of its own parameters.

The ``name`` attributes is mapped to the section name of the service in
the Service file.

Each parameters can be accessed either as a dictionnary entry or as an
attributes.

.. code:: python

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

class ``pgtoolkit.service.ServiceFile()``
-----------------------------------------

``ServiceFile`` class implements access, parsing and rendering of
service file.

``ServiceFile.add(service)`` adds a ```Service`` <#service>`__ object to
the service file.

``ServiceFile.parse(fo, source=None)`` method is strictly the same as
```parse`` <#parse>`__ function. It’s the method counterpart.

``ServiceFile.save(fo)`` writes services in ``fo`` file-like object.

!!! note

::

    Comments are not preserved.

``ServiceFile`` is subscriptable. You can access service using
``servicefile['servicename']`` syntax.

.. autofunction:: pgtoolkit.service.find


Examples
--------

How to edit a service file:

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

How to use a service file to connect with psycopg2:

.. code:: python

    from pgtoolkit.service import find, parse
    from psycopg2 import connect

    servicefilename = find()
    with open(servicefile) as fo:
        servicefile = parse(fo, source=servicefilename)
    connection = connect(**servicefile['myservice'])

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
        self.config.remove_section(service.name)
        self.config.add_section(service.name)
        for parameter, value in service.items():
            self.config.set(service.name, parameter, str(value))

    def parse(self, fo, source=None):
        self.config.read_file(fo, source=source)

    def save(self, fo):
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

    :param environ: Dict of environment variables.

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
