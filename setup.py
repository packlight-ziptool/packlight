from pathlib import Path

import setuptools


README = Path("README.md").read_text(encoding="utf-8")


setuptools.setup(
    name="packlight",
    version="0.1.0",
    description="Create ZIP archives from local folders while skipping common clutter.",
    long_description=README,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    packages=["packlight"],
    python_requires=">=3.9",
    install_requires=[],
    keywords=["zip", "archive", "macos", "finder", "cli", "local-first", "verified"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Operating System :: MacOS",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: System :: Archiving :: Packaging",
    ],
    entry_points={
        "console_scripts": ["packlight = packlight.cli:main"],
    },
)
