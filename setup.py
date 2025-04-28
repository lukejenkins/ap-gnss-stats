#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="ap-gnss-stats",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'parse-gnss-logs=ap_gnss_stats.bin.parse_logs:main',
        ],
    },
    install_requires=[],
    python_requires='>=3.6',
    author="Luke Jenkins",
    author_email="your.email@example.com",
    description="Tools for parsing and analyzing GNSS statistics from Cisco Access Points",
    keywords="cisco, gnss, ap, wireless, parsing",
    url="https://github.com/lukejenkins/ap-gnss-stats",
    project_urls={
        "Bug Tracker": "https://github.com/lukejenkins/ap-gnss-stats/issues",
        "Source Code": "https://github.com/lukejenkins/ap-gnss-stats",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Networking :: Monitoring",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)