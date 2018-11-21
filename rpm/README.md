# Building RPM Package

With docker-compose, you can build a RPM package for pgtoolkit in a few steps.
To build for CentOS 6, ensure `dist/` contains source tarball from PyPI.

``` console
$ make all push
```

The spec file is based on [Devrim Günduz](https://twitter.com/DevrimGunduz)
packaging for pgspecial.
