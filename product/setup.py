"""Codebase Health Monitor — Git repository health analytics."""

from setuptools import setup, find_packages

setup(
    name="chm",
    version="0.1.0",
    description="Illuminate the dark corners of your codebase",
    author="Lighthouse Analytics",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "jinja2>=3.0",
    ],
    entry_points={
        "console_scripts": [
            "chm=chm.cli:main",
        ],
    },
    python_requires=">=3.9",
)
