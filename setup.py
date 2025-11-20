"""Setup script for the EnerGIS Planning Framework."""

from pathlib import Path
from setuptools import setup, find_packages

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file) as f:
        requirements = [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ]

setup(
    name="energis",
    version="2.0.0-alpha",
    description="Modular MILP Framework for Industrial Heat Network Planning",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="EnerGIS Team",
    author_email="",
    url="https://github.com/LukasRuess98/Planing-Framework-for-Heat",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "examples", "notebooks"]),
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
        "notebooks": [
            "pandas>=1.5.0",
            "numpy>=1.23.0",
            "ipykernel>=6.0.0",
            "ipywidgets>=8.0.0",
        ],
        "full": [
            "pyomo>=6.0.0",
            "matplotlib>=3.5.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "energis=energis.run.__main__:main",
        ],
    },
)
