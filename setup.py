from setuptools import setup


metadatas = dict(
    name='pgtoolkit',
    description='Manage Postgres cluster files from Python',
    version='0.0.1a0',
    author='Dalibo',
    author_email='contact@dalibo.com',
    license='PostgreSQL',
)


if __name__ == '__main__':
    setup(
        packages=['pgtoolkit'],
        **metadatas
    )
