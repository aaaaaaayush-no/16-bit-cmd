"""Setup configuration for the debug16 package."""

from setuptools import setup, find_packages

setup(
    name="debug16",
    version="1.0.0",
    description="A faithful replica of the classic 16-bit MS-DOS DEBUG.COM debugger",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "unicorn>=2.0.0",
        "keystone-engine>=0.9.2",
        "capstone>=5.0.0",
        "prompt_toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "debug16=debug16.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Debuggers",
        "Topic :: System :: Emulators",
    ],
)
