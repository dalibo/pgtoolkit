# Building RPM Package

With docker-compose, you can build a RPM package for pgtoolkit in a few steps.

``` console
$ make all push
```

The spec file is based on [Devrim Günduz](https://twitter.com/DevrimGunduz)
packaging for pgspecial.

The version in `rpm/python-pgtoolkit.spec` file may need to be updated.
