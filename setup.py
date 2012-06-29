# encoding: utf-8
import os
from setuptools import setup, find_packages

requires = [
    'fabric',
    'argparse',
    'simplejson',
    ]

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

setup(
    name='muppet',
    version='0.0',
    description='Muppet server configuration tool',
    long_description=README + '\n\n' +  CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Topic :: System :: Clustering",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
        ],
    author='Moriyoshi Koizumi',
    author_email='mozo@mozo.jp',
    url='',
    keywords='muppet',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    include_package_data=True,
    zip_safe=True,
    install_requires=requires,
    tests_require=requires,
    entry_points = {
        'console_scripts': (
            'muppet = muppet.scripts.muppet_:main',
        )
    }
    )
