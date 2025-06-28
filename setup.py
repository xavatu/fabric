from setuptools import setup, find_packages

setup(
    name="fabric",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "SQLAlchemy==2.0.41",
        "fastapi==0.115.14",
        "setuptools==80.9.0",
    ],
)
