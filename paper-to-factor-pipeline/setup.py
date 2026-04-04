"""Setup script for paper_to_factor package."""

from setuptools import find_packages, setup


setup(
    name="paper_to_factor",
    version="0.1.0",
    description="Autonomous algorithmic trading research system",
    author="Paper-to-Factor Pipeline",
    packages=find_packages(include=["src", "src.*"]),
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "yfinance>=0.2.36",
        "arxiv>=2.1.0",
        "mcp>=1.0.0",
        "scikit-learn>=1.3.0",
        "xgboost>=2.0.0",
        "PyYAML>=6.0",
        "pytest>=7.4.0",
        "pyarrow>=10.0.0",
    ],
)
