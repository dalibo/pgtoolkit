import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent

with (here / "README.rst").open("r", encoding="utf-8") as fo:
    long_description = fo.read()

metadatas = dict(
    name="pgtoolkit",
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
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    install_requires=[
        "typing_extensions",
    ],
)


if __name__ == "__main__":
    setup(
        packages=find_packages("."),
        package_data={"pgtoolkit": ["py.typed"]},
        python_requires=">=3.6",
        **metadatas
    )
