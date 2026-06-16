"""Codebase Health Monitor — Git repository health analytics."""

from setuptools import setup, find_packages

with open("README.md") as f:
    long_description = f.read()

setup(
    name="chm-cli",
    version="0.2.0",
    description="Illuminate the dark corners of your codebase — one command to know your codebase health",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Lighthouse Analytics",
    author_email="hello@lighthouse-analytics.dev",
    url="https://github.com/lighthouse/chm",
    project_urls={
        "Documentation": "https://lighthouse-analytics.dev/docs",
        "Source": "https://github.com/lighthouse/chm",
        "Issues": "https://github.com/lighthouse/chm/issues",
    },
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "click>=8.0",
        "jinja2>=3.0",
    ],
    extras_require={
        "mcp": ["mcp>=1.0"],
        "dev": ["pytest>=7.0", "build"],
    },
    entry_points={
        "console_scripts": [
            "chm=chm.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    python_requires=">=3.9",
)
