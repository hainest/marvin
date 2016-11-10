# Marvin
Marvin is the ultimate tool to visualise and analyse MaNGA data. It is developed and maintained by the MaNGA team.

[![Build Status](https://travis-ci.org/sdss/marvin.svg?branch=master)](https://travis-ci.org/sdss/marvin)
[![Coverage Status](https://coveralls.io/repos/github/sdss/marvin/badge.svg?branch=master)](https://coveralls.io/github/sdss/marvin?branch=master)
[![PyPI](https://img.shields.io/pypi/v/sdss-marvin.svg)](https://pypi.python.org/pypi/sdss-marvin)
[![PyPI](https://img.shields.io/pypi/dm/sdss-marvin.svg)](https://pypi.python.org/pypi/sdss-marvin)

Installation
------------

To painlessly install Marvin:

    pip install sdss-marvin

If `pip install sdss-marvin` does not install Marvin's dependencies:

    wget https://raw.githubusercontent.com/sdss/marvin/master/requirements.txt
    pip install -r requirements.txt
    pip install sdss-marvin

If you don't have `wget`, you can try:

    git clone https://github.com/sdss/marvin
    cd marvin
    pip install -r requirements.txt
    pip install sdss-marvin

Alternatively, you can clone this git repo and run python setup install:

    git clone https://github.com/sdss/marvin
    cd marvin
    git submodule init
    git submodule update
    python setup.py install

What is Marvin?
---------------

Marvin is a complete ecosystem designed for overcoming the challenge of
searching, accessing, and visualizing the MaNGA data. It consists of a
three-pronged approach of a web app, a python package, and an API. The web app,
Marvin-web, provides an easily accessible interface for searching the MaNGA data
and visual exploration of individual MaNGA galaxies or of the entire sample. The
python package, in particular Marvin-tools, allows users to easily and
efficiently interact with the MaNGA data via local files, files retrieved from
the [Science Archive Server](https://sas.sdss.org), or data directly grabbed
from the database.  The tools come mainly in the form of convenience functions
and classes for interacting with the data. An additional tool is a powerful
query functionality that uses the API to query the MaNGA databases and return
the search results to your python session. Marvin-API is the critical link that
allows Marvin-tools and Marvin-web to interact with the databases, which enables
users to harness the statistical power of the MaNGA data set.