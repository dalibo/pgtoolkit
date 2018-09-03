all:

VERSION=$(python setup.py --version)
GIT_UPSTREAM=git@github.com:dalibo/pgtoolkit.git
release:
	git commit setup.py -m "Version $(VERSION)"
	git tag $(VERSION)
	git push $(GIT_UPSTREAM) master
	git push --tags $(GIT_UPSTREAM)
	python setup.py sdist bdist_wheel --universal
	twine upload dist/pgtoolkit-$(VERSION).tar.gz dist/pgtoolkit-$(VERSION)-*.whl
