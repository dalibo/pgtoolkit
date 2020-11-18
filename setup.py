from setuptools import setup


metadatas = dict(
    name='pgtoolkit',
    description='Postgres Support from Python',
    version='0.10.0',
    author='Dalibo',
    author_email='contact@dalibo.com',
    url='https://github.com/dalibo/pgtoolkit',
    license='PostgreSQL',
)


if __name__ == '__main__':
    setup(
        packages=['pgtoolkit'],
        package_data={'pgtoolkit': ['py.typed']},
        python_requires=">=3.6",
        **metadatas
    )
