try:
    # Use setuptools for bdist_wheel and other extension.
    from setuptools import setup
except ImportError:
    # Let's try distutils for rpm build/install.
    from distutils.core import setup


metadatas = dict(
    name='pgtoolkit',
    description='Manage Postgres cluster files from Python',
    version='0.0.1a1',
    author='Dalibo',
    author_email='contact@dalibo.com',
    license='PostgreSQL',
)


if __name__ == '__main__':
    setup(
        packages=['pgtoolkit'],
        **metadatas
    )
