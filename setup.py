from setuptools import setup, find_packages
import os

try:
    with open("README.md", "r") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = ""

branch = os.getenv('GITHUB_REF', 'master').split('/')[-1]  # Default to 'master' if GITHUB_REF is not set
url = f"https://github.com/armurox/loggingredactor/tree/{branch}"

# Get version from environment variable
version = os.getenv('RELEASE_VERSION', '0.0.5')  # Default to '0.0.4' if RELEASE_VERSION is not set
# Get development status
split_version = version.split('-')
if len(split_version) == 2:
    release_mode = split_version[1][0].upper()
    status = {
        'P': '1 - Planning',
        'R': '2 - Pre-Alpha',
        'A': '3 - Alpha',
        'B': '4 - Beta'
    }.get(release_mode)
else:
    status = '5 - Production/Stable'

setup(
    name="loggingredactor",
    packages=find_packages(),
    version=version,
    url=url,
    description="Redact data in logs based on regex filters and keys",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Arman Jasuja",
    author_email="arman_jasuja@yahoo.com",
    classifiers=[
        f"Development Status :: {status}",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires='>=3.7',
)
