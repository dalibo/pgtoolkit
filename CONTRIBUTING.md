# Contributing to pgtoolkit

You're welcome to contribute to pgtoolkit with code and more like issue, review,
documentation and spreading the word!

pgtoolkit home for contribution is it's [GitHub project
page](https://github.com/dalibo/pgtoolkit). Use issue, PR and comments to get in
touch with us!


## Releasing a new version

To release a new version you'll need:

- read-write access to GitHub project https://github.com/dalibo/pgtoolkit ;
- maintainer access to https://pypi.org/project/pgtoolkit/ ;
- [twine](https://github.com/pypa/twine) installed and setup for pypi upload ;
- setuptools and [wheel](https://github.com/pypa/wheel); virtualenv installs
  them by default in any new venv.

Then, follow the next steps:

- Edit `setup.py` and set the new version in metadata.
- Do the same in `rpm/python-pgtoolkit.spec`.
- Run `make release`. The new source archive is available at
  [PyPI](https://pypi.org/project/pgtoolkit/).
- Follow instructions to [build rpm](./rpm) and upload to [Dalibo
  Labs](https://yum.dalibo.org/labs/).
- Edit `setup.py` and set the new development version with the suffix `.dev0`.
- Run `python setup.py egg_info` to regenerate your metadatas.
