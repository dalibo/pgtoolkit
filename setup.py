from setuptools import setup


with open("README.rst", "r", encoding="utf-8") as fo:
    long_description = fo.read()

metadatas = dict(
    name="pgtoolkit",
    version="0.13.0",
    description="PostgreSQL Support from Python",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author="Dalibo",
    author_email="contact@dalibo.com",
    url="https://github.com/dalibo/pgtoolkit",
    license="PostgreSQL",
    keywords="postgresql postgresql.conf pg_hba pgpass pg_service.conf",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: PostgreSQL License",
        "Programming Language :: Python :: 3",
        "Topic :: Database",
    ],
)


if __name__ == "__main__":
    setup(
        packages=["pgtoolkit"],
        package_data={"pgtoolkit": ["py.typed"]},
        python_requires=">=3.6",
        **metadatas
    )
