from setuptools import find_packages, setup

setup(
    name="pipeline",
    version="0.1.0",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "dagster>=1.7,<2.0",
        "dagster-webserver>=1.7,<2.0",
        "dagster-postgres>=0.23,<1.0",
        "dagster-duckdb>=0.23,<1.0",
        "minio>=7.2",
        "great-expectations>=1.0,<2.0",
        "requests>=2.31",
        "duckdb>=0.10",
        "pandas>=2.0",
        "pyarrow>=14.0",
        "ruff",
        "pytest",
    ],
)
