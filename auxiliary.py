"""
proyectero: a small project management tool for py4web

This is the MVP of the project "Proyectero". Developed at
Escuela Técnica 29 DE 6 "Reconquista de Buenos Aires"
Buenos Aires - Argentina

Released under Affero GNU Public License version 3. See "LICENSE"

Auxiliar module: for storing non-mvc taxative stuff
"""

from .common import T
from py4web.utils.grid import *

TEAM_ACTIONS = {"tasks": T("Tasks"), "gantt": T("Gantt chart"),
                "delphi_panel": T("Wideband-delphi"),
                "cpm": T("Critical Path Method (CPM)"),
                "s_curve": T("S-curve"),
                "kanban_board": T("Kanban board"),
                "log": T("Project's log")}

ADMIN_ACTIONS = {"project_edit": T("Edit project"),
                 "admins_add": T("Add admins"),
                 "team_add": T("Add team members"),
                 "admins_remove": T("Remove admins"),
                 "team_remove": T("Remove team members"),
                 "phases": T("Project phases"),
                 "stages": T("Project stages"),
                 "links": T("Link tasks"),
                 "budget": T("Project budget")}

# auxiliar function of s_curve
# returns the sum of anything in obj before or as to date
def accumulated(date, obj):
    total = 0.0
    for key in obj:
        if key <= date:
            total += obj[key]
    return total

# auxiliar function to search for the better
# progress state before a date
# for s_curve
def accumulated_lookup(date, obj):
    value = 0.0
    for k in obj:
        if ((k < date) and (obj[k] > value)):
            value = obj[k]
    return value

def t_wrapper(obj):
    # A workaround for elements that
    # do not support translations
    if type(obj) == Grid:
        f = obj.form
        if not f:
            return obj
    else:
        f = obj
    inputs = f.structure.find("input[type=submit]")
    if inputs:
        inputs[0].attributes["_value"] = T("Submit")
    labels = f.structure.find("label.help")
    if labels:
        labels[0].children = " " + T("Check to delete")            
    return obj