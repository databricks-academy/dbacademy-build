import setuptools
from setuptools import find_packages

def find_dbacademy_packages():
    packages = find_packages(where="src")
    if "dbacademy" in packages:
        del packages[packages.index("dbacademy")]
    # print("-"*80)
    # print(packages)
    # print("-"*80)
    return packages


setuptools.setup(
    name="dbacademy-courseware",
    version="0.1",
    package_dir={"": "src"},
    packages=find_dbacademy_packages(),
    install_requires=[
        "requests",
        "dbacademy-rest@git+https://github.com/databricks-academy/dbacademy-gems",
        "dbacademy-rest@git+https://github.com/databricks-academy/dbacademy-rest",
    ],
)
