#!/usr/bin/env python3
import os,sys

if 'posix' not in os.name:
    status = 'Dust has only been tested with on Linux. Exiting'
    raise Exception(status) 

from setuptools import setup
import dustcluster

required_packages = [
    'paramiko>=2.7.1',
    'pyyaml>=5.1',
    'boto3>=1.12.0',
    'boto>=2.49.0',
    'troposphere>=1.5.0',
    'colorama>=0.3.5'
    ]

setup(
    name = "dustcluster",
    version = dustcluster.__version__,
    author = "R Dugal",
    author_email = "dugal@gmx.com",
    url='https://github.com/carlsborg/dust',
    description = "ssh cluster shell for AWS EC2",
    license = "GPL Affero",
    install_requires = required_packages,
    packages=['dustcluster','dustcluster/commands'],
    scripts = ['bin/dust'],
    python_requires='>=3.0.0',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Information Technology',
        'Natural Language :: English',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities'
        ]
    )

