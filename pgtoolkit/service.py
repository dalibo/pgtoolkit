# cf. https://www.postgresql.org/docs/current/static/libpq-pgservice.html

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


def find(environ=os.environ):
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
