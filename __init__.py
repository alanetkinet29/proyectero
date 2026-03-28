"""
proyectero: a small project management tool for py4web

This is the MVP of the project "Proyectero". Developed at
Escuela Técnica 29 DE 6 "Reconquista de Buenos Aires"
Buenos Aires - Argentina

Released under Affero GNU Public License version 3. See "LICENSE"
"""

# check compatibility
import py4web

assert py4web.check_compatible("1.20190709.1")

# by importing controllers you expose the actions defined in it
from . import controllers

# by importing db you expose it to the _dashboard/dbadmin
from .models import db

# import the scheduler
from .tasks import scheduler

# optional parameters
__version__ = "0.0.1"
__author__ = "Alan Edmundo Etkin <alanedmundo.etkin@tecnica29de6.edu.ar>"
__license__ = "AGPLv3"
