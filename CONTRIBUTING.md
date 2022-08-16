# Contributing to pgtoolkit

You're welcome to contribute to pgtoolkit with code and more like issue, review,
documentation and spreading the word!

pgtoolkit home for contribution is it's [GitHub project
page](https://github.com/dalibo/pgtoolkit). Use issue, PR and comments to get in
touch with us!


## Releasing a new version

To release a new version you'll need read-write access to GitHub project
https://github.com/dalibo/pgtoolkit

Then, follow the next steps:

- Update version in `rpm/python-pgtoolkit.spec` file, commit the changes
- Create an annotated (and optionally signed) tag
  `git tag -a [-s] -m "pgtoolkit <version>" <version>`
- Push the new tag
  `git push --follow-tags`
- Then the new release will be available at
  [PyPI](https://pypi.org/project/pgtoolkit/)
  (after GitHub publish workflow is finished)
- Follow instructions to [build rpm](./rpm) and upload to [Dalibo
  Labs](https://yum.dalibo.org/labs/).
