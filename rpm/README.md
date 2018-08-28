# Building RPM Package

With docker-compose, you can build a RPM package for pgtoolkit in a few steps.

``` console
$ docker-compose run --rm centos7
```

The rpm is available in `dist/noarch/` directory.

To build for CentOS 6, ensure `dist/` contains source tarball from PyPI, then
use `centos6` service :

``` console
$ docker-compose run --rm centos6
```

To upload to Dalibo Labs YUM repository, contact Dalibo Labs YUM maintainers.

The spec file is based on Devrim Günduz packaging for pgspecial.
