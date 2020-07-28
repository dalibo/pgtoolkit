from setuptools import setup


metadatas = dict(
    name='pgtoolkit',
    description='Postgres Support from Python',
    version='0.7.3',
    author='Dalibo',
    author_email='contact@dalibo.com',
    url='https://github.com/dalibo/pgtoolkit',
    license='PostgreSQL',
)


if __name__ == '__main__':
    setup(
        packages=['pgtoolkit'],
        **metadatas
    )
