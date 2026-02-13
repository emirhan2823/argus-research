from setuptools import setup, find_packages

setup(
    name="argus",
    version="2.5.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "ccxt",
        "pandas_ta",
        "python-dotenv",
        "arch",
        "polars",
        "pyarrow",
        "scikit-learn"
    ],
)
