#!/usr/bin/env python
import os,sys

    
if sys.version <= '2.6' or sys.version >= '3.0':
    status = 'Dust has only been tested with Python 2.7. Your version is %s. Exiting' % sys.version.split()[0]
    raise Exception(status) 

if 'posix' not in os.name:
    status = 'Dust has only been tested with on Linux. Exiting'
    raise Exception(status) 

from distutils.core import setup
import dustcluster

required_packages = [
    'paramiko',
    'pyyaml',
    'boto>=2.39.0',
    'troposphere>=1.5.0',
	'colorama>=0.2.5,<=0.3.3'
    ]

setup(
    name = "dustcluster",
    version = dustcluster.__version__,
    author = "R Dugal",
    author_email = "dugal@gmx.com",
    url='https://github.com/carlsborg/dust',
    description = "ssh cluster shell for AWS EC2",
    license = "GPL Affero",
    packages=['dustcluster','dustcluster/commands'],
    scripts = ['bin/dust'],
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
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities'
        ]
    )

