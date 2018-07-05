=================
pgtoolkit.service
=================

See `The Connection Service File
<https://www.postgresql.org/docs/current/static/libpq-pgservice.html>`__ in
PostgreSQL documentation.

``pgtoolkit.service.parse(fo, source=None) -> ServiceFile``
-----------------------------------------------------------

``parse()`` accepts a file-object as returned by open. Actually it only
requires an iterable object yielding each lines of the file. You can
provide ``source`` to have more precise error message.

!!! note

::

    pgtoolkit is less strict than `libpq`. `libpq` does not accepts spaces
    around equals.  pgtoolkit accepts them but do not write them.

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

``pgtoolkit.service.find(environ=os.environ)``
----------------------------------------------

``find()`` search for the first candidate of ``pg_service.conf`` file
from either environment and regular locations. ``find`` raises an
exception if it fails to find a Connection service file.

.. code:: python

    from pgtoolkit.service import find

    try:
        servicefile = find()
    except Exception as e:
        "Deal with exception."
    else:
        "Manage servicefile."

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
