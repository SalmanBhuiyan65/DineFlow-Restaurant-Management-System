"""Sphinx configuration for DineFlow Restaurant Management System."""

import os
import sys
import django

sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dineflow.settings')
django.setup()

project = 'DineFlow Restaurant Management System'
author = 'Salman, Orin, Hasibul (CSE 451)'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
html_theme = 'sphinx_rtd_theme'
