#!/usr/bin/env python

import setuptools
from version import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

# update the local links, so that the documentation on PyPi points to Github
long_description = long_description.replace(
    "](bin",      "](https://github.com/eegsynth/eegsynth/raw/master/bin")
long_description = long_description.replace(
    "](doc",      "](https://github.com/eegsynth/eegsynth/raw/master/doc")
long_description = long_description.replace(
    "](hardware", "](https://github.com/eegsynth/eegsynth/raw/master/hardware")
long_description = long_description.replace(
    "](lib",      "](https://github.com/eegsynth/eegsynth/raw/master/lib")
long_description = long_description.replace(
    "](module",   "](https://github.com/eegsynth/eegsynth/raw/master/module")
long_description = long_description.replace(
    "](patches",  "](https://github.com/eegsynth/eegsynth/raw/master/patches")

# The organization of the Python code is non-standard, hence a custom
# package_dir and packages specification is needed.

setuptools.setup(
    name="eegsynth",
    version=__version__,
    description="Converting real-time EEG into sounds, music and visual effects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://www.eegsynth.org",
    author="Robert Oostenveld",
    author_email="r.oostenveld@gmail.com",
    license="GPLv3",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Artistic Software",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
    ],
    keywords=[
        "EEG",
        "EMG",
        "ECG",
        "BCI",
        "brain",
        "art",
        "music",
        "sound",
        "sonification",
        "brain-computer interface",
        "real-time",
    ],
    project_urls={
        "Documentation": "https://github.com/eegsynth/eegsynth/blob/master/doc/README.md",
        "Source": "https://github.com/eegsynth/eegsynth/",
        "Tracker": "https://github.com/eegsynth/eegsynth/issues",
    },
    package_dir={"eegsynth": ".", "eegsynth.bin": "bin", "eegsynth.lib": "lib", "eegsynth.module": "module"},
    packages=["eegsynth"] + ["eegsynth." + s for s in setuptools.find_packages(".")],
    install_requires=[
        "bleak",
        "colorama",
        "configparser",
        "fuzzywuzzy[speedup]",
        "matplotlib",
        "mido",
        "nilearn",
        "numpy",
        "opencv-python",
        "paho-mqtt",
        "pandas",
        "pyaudio",
        "pylsl",
        "PyQt5",
        "pyqtgraph==0.12",
        "pyserial",
        "pyzmq",
        "redis",
        "scipy",
        "scikit-learn",
        "termcolor",
        "wiringpi; platform_machine == 'armv7l'"
    ],
    python_requires=">=2.7",
    extras_require={
        ":python_version<'3.5'": ["pyOSC"],
        ":python_version>='3.5'": ["python-rtmidi"],
        ":python_version>='3.5'": ["python-osc"]
    },
    entry_points={
        'console_scripts': [
            'eegsynth = eegsynth.bin.eegsynth:_executable'
        ],
    },
)
