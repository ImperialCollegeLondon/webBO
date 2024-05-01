:Authors: - Austin Mroz
:Documentation: https://webbo.readthedocs.io


Overview
========

`IDOS` is the Imperial Data-driven Optimization System. This platform
facilitates the chemical and materials discovery platforms that are
available at Imperial College London.

Installation
============

Installation instructions:: bash

.. code-block:: bash

  $ conda create -p ./.venv python=3.11
  $ conda activate ./.venv
  $ pip install baybe
  $ pip install Flask
  $ pip install sqlalchemy
  $ pip install Flask-SQLAlchemy
  $ pip install flask-login
  $ pip install dash
  $ pip install 'baybe[chem]'
  $ pip install flask-wtf
  $ pip install datalab-api
  $ pip install lxml

Acknowledgements
================

`Austin Mroz`__ developed this while funded as an `Eric and Wendy Schmidt AI in
Science Fellow`__ at `IX`__

__ https://github.com/austin-mroz
__ https://www.schmidtfutures.com/our-work/schmidt-ai-in-science-postdocs/
__ https://ix.imperial.ac.uk/
