"""
    :copyright: 2021 Inmanta
    :contact: code@inmanta.com
    :license: Inmanta EULA
"""
from pathlib import Path
from setuptools import setup, find_packages

setup(
    # Package info
    name="inmanta-tfplugin5",
    version="0.0.1",
    author="Inmanta",
    author_email="code@inmanta.com",
    url="https://github.com/inmanta/terraform",
    license="Inmanta EULA",
    description="Side generated package for the terraform handler",

    # Package content
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Framework :: Pytest",
    ],
    install_requires=Path("requirements.txt").read_text().split("\n"),
    entry_points={"pytest11": ["inmanta-tfplugin5 = tfplugin5"]},
)
