"""
This file defines the database models
"""

from pydal.validators import *

from .common import Field, db

# libraries imported by the project
from yatl.helpers import XML
import datetime
from decimal import Decimal
from .common import T
from .common import auth

### Define your table below
#
# db.define_table('thing', Field('name'))
#
## always commit your models to avoid problems later
#
# db.commit()
#

NOW = datetime.datetime.now()
STATUSES = {"closed": T("Closed"),
            "in_progress": T("Work in progress")}

TASK_STATUSES = {"pending": T("Pending"), "in_progress": T("In progress"),
                                     "done": T("Done")}

CATHEGORIES = {"taxes": T("taxes"), "services": T("services"),
               "staff": T("staff"), "advice": T("advice"),
               "loans": T("loans"), "equipment": T("equipment"),
               "supplies": T("supplies"),
               "purchases": T("purchases"), "other": T("other")}

db.define_table("project",
                Field("name"),
                Field("organization"),
                Field("description", "text"),
                Field("start", "datetime"),
                Field("status"),
                Field("admins", "list:reference auth_user"),
                Field("team", "list:reference auth_user"),
                Field("budget", "decimal(15, 2)"),
                Field("progress", "double"),
                Field("deadline", "datetime"),
                format="%(name)s"
                )
    
db.define_table("phase",
                Field("name"),
                Field("label"),
                Field("description", "text"),
                Field("project", "reference project"),
                format="%(name)s"
                )

db.define_table("stage",
                Field("name"),
                Field("label"),
                Field("description", "text"),                 
                Field("phase", "reference phase"),
                format="%(name)s"
                )

db.define_table("task",
                Field("name"),
                Field("label"),
                Field("description", "text"),
                Field("tags", "list:string"),
                Field("stage", "reference stage"),
                Field("status"),
                Field("start", "datetime"),
                Field("months", "integer"),
                Field("days", "integer"),
                Field("hours", "integer"),
                Field("minutes", "integer"),
                Field("end", "datetime"),
                Field("estimated", "double"), # time required in hours
                Field("team", "list:reference auth_user"),
                format="%(name)s"
                )

db.define_table("log",
                Field("title"),
                Field("body", "text"),
                Field("date", "datetime"),
                Field("project", "reference project"),
                Field("task", "reference task"),
                Field("author", "reference auth_user"),
                Field("tags", "list:string")
                )

db.define_table("link",
                Field("project", "reference project"),
                Field("parent_table"), # one of phase, stage or task
                Field("parent_id", "integer"), # the record id
                Field("child_table"), # same as parent_kind
                Field("child_id", "integer") # the record id
                )

db.define_table("delphi",
                Field("task", "reference task"),
                Field("experts", "list:reference auth_user"),
                Field("rounds", "integer"), # number of sequenced estimations
                Field("start", "datetime"),
                Field("days", "integer"), # window
                Field("hours", "integer"),# window
                Field("minutes", "integer"),# window
                Field("window", "double"), # computed window (hours)
                Field("estimated", "double") # final estimated (hours)
                )

db.define_table("estimation",
                Field("task", "reference task"),
                Field("round", "integer"), # which round it belongs to
                Field("months", "integer"), # estimated
                Field("days", "integer"), # estimated
                Field("hours", "integer"), # estimated
                Field("minutes", "integer"), # estimated
                Field("estimated", "double"), # computed estimation in hours
                Field("expert", "reference auth_user")
                )

db.define_table("budget",
                Field("project", "reference project"),
                Field("author", "reference auth_user"),
                Field("entry"),
                Field("description", "text"),
                Field("cathegory"),
                Field("start", "datetime"),
                Field("finish", "datetime"),
                Field("quantity", "integer"),
                Field("unit", "decimal(10, 2)"),
                Field("amount", "decimal(10, 2)"),
                format = "%(entry)s"
                )

# db.stage.name uniqueness should be filtered on insert or update forms
# by project
# The same with db.phase about stages
# The same for db.task.name about phases
# The same for db.task.name about phases
# any auth_user related validator should be set
# against session context variables such as organization and project

def estimated_compute(row):
    # add each time field converting them to
    # hours before
    value = 0
    convert = dict(years=365*24, months=30*24, days=24, hours=1, minutes=1/60, seconds=1/3600)
    for key in ("years", "months", "days", "hours", "minutes", "seconds"):
        if (key in row) and (type(row[key]) == int):
            value += row[key]*convert[key]
    return value

def budget_compute(row):
    return row["quantity"] * row["unit"]

def link_id_represent(value, row):
    parent = db(db[row.parent_table].id == row.parent_id).select().first()
    child = db(db[row.child_table].id == row.child_id).select().first()
    parent_name = child_name = None
    # Default to None in case there are broken
    # references
    if parent:
        parent_name = parent.name
    if child:
        child_name = child.name
    return "(#%d) %s -> %s" % (value,
                               parent_name, child_name)

def task_stage_represent(value, row):
     stage = db(db.stage.id == value).select().first()
     phase = db(db.phase.id == stage.phase).select().first()
     return "%s (%s)" % (stage.name, phase.name)

def task_stage_format(value):
    stage = db(db.stage.id == value).select().first()
    phase = db(db.phase.id == stage.phase).select().first()
    return "%s (%s)" % (stage.name, phase.name)

def link_cleanup():
    # TODO: to be called when a phase, stage or task is deleted
    # so any related link is removed
    pass

db.project.status.default = "in_progress"
db.project.status.requires = IS_IN_SET(STATUSES)
db.project.name.requires = [IS_NOT_EMPTY(), IS_NOT_IN_DB(db, "project.name")]
db.project.start.default = NOW
db.project.start.requires = [IS_NOT_EMPTY(), IS_DATETIME()]
db.project.progress.writable = False

db.budget.cathegory.requires = IS_IN_SET(CATHEGORIES)
db.budget.project.writable = False
db.budget.author.writable = False
db.budget.quantity.default = 1
db.budget.quantity.requires = IS_INT_IN_RANGE(1, 1000000000)
db.budget.unit.default = Decimal("0.00")
db.budget.amount.writable = False
db.budget.amount.compute = budget_compute
db.budget.entry.requires = IS_NOT_EMPTY()
db.budget.start.default = NOW
db.budget.finish.default = NOW
db.budget.cathegory.default = "staff"

db.task.name.requires = IS_NOT_EMPTY()
db.task.months.requires = IS_INT_IN_RANGE(0, 12)
db.task.months.default = 0
db.task.days.requires = IS_INT_IN_RANGE(0, 31)
db.task.days.default = 0
db.task.hours.requires = IS_INT_IN_RANGE(0, 24)
db.task.hours.default = 0
db.task.minutes.requires = IS_INT_IN_RANGE(0, 60)
db.task.minutes.default = 0
db.task.estimated.writable = False
db.task.tags.comment = T("Type as much tags as you want here, press TAB key to add the to the list")
db.task.estimated.compute = estimated_compute
db.task.stage.comment = T("Stage. This field is mandatory")
db.task.stage.represent = task_stage_represent
db.task.status.requires = IS_IN_SET(TASK_STATUSES)
db.task.status.represent = lambda v, r: TASK_STATUSES[v]
db.task.status.default = "pending"

db.delphi.days.requires = IS_INT_IN_RANGE(0, 31)
db.delphi.days.default = 0
db.delphi.hours.requires = IS_INT_IN_RANGE(0, 24)
db.delphi.hours.default = 0
db.delphi.minutes.requires = IS_INT_IN_RANGE(0, 60)
db.delphi.minutes.default = 0
db.delphi.rounds.requires=IS_INT_IN_RANGE(1, 20)
db.delphi.rounds.default = 1
db.delphi.window.compute = estimated_compute

db.estimation.months.requires = IS_INT_IN_RANGE(0, 12)
db.estimation.months.default = 0
db.estimation.days.requires = IS_INT_IN_RANGE(0, 31)
db.estimation.days.default = 0
db.estimation.hours.requires = IS_INT_IN_RANGE(0, 24)
db.estimation.hours.default = 0
db.estimation.minutes.requires = IS_INT_IN_RANGE(0, 60)
db.estimation.minutes.default = 0
db.estimation.estimated.compute = estimated_compute

db.stage.phase.comment = T("Phase. This field is mandatory")
db.stage.phase.requires = [IS_NOT_EMPTY(), IS_IN_DB(db,
            db.phase.id, db.phase._format)]


db.link.id.represent = link_id_represent

db.delphi.days.comment = T("Time window between rounds in days")
db.delphi.hours.comment = T("Time window between rounds in hours")
db.delphi.minutes.comment = T("Time window between rounds in minutes")

db.estimation.expert.writable = False
db.estimation.task.writable = False
db.estimation.round.writable = False
db.estimation.estimated.readable = False
db.estimation.estimated.writable = False

#############################################################
# field name translations
#############################################################

db.auth_user.id.label = T("Id")
db.auth_user.username.label = T("Username")
db.auth_user.email.label = T("Email")
db.auth_user.password.label = T("Password")
db.auth_user.first_name.label = T("First Name")
db.auth_user.last_name.label = T("Last Name")
db.auth_user.sso_id.label = T("Sso Id")
db.auth_user.action_token.label = T("Action Token")
db.auth_user.last_password_change.label = T("Last Password Change")
db.auth_user.past_passwords_hash.label = T("Past Passwords Hash")
db.auth_user_tag_groups.id.label = T("Id")
db.auth_user_tag_groups.tagpath.label = T("Tagpath")
db.auth_user_tag_groups.record_id.label = T("Record Id")
db.project.id.label = T("Id")
db.project.name.label = T("Name")
db.project.organization.label = T("Organization")
db.project.description.label = T("Description")
db.project.start.label = T("Start")
db.project.status.label = T("Status")
db.project.admins.label = T("Admins")
db.project.team.label = T("Team")
db.project.budget.label = T("Budget")
db.project.progress.label = T("Progress")
db.project.deadline.label = T("Deadline")
db.phase.id.label = T("Id")
db.phase.name.label = T("Name")
db.phase.label.label = T("Label")
db.phase.description.label = T("Description")
db.phase.project.label = T("Project")
db.stage.id.label = T("Id")
db.stage.name.label = T("Name")
db.stage.label.label = T("Label")
db.stage.description.label = T("Description")
db.stage.phase.label = T("Phase")
db.task.id.label = T("Id")
db.task.name.label = T("Name")
db.task.label.label = T("Label")
db.task.description.label = T("Description")
db.task.tags.label = T("Tags")
db.task.stage.label = T("Stage")
db.task.status.label = T("Status")
db.task.start.label = T("Start")
db.task.months.label = T("Months")
db.task.days.label = T("Days")
db.task.hours.label = T("Hours")
db.task.minutes.label = T("Minutes")
db.task.end.label = T("End")
db.task.estimated.label = T("Estimated (hours)")
db.task.team.label = T("Team")
db.log.id.label = T("Id")
db.log.title.label = T("Title")
db.log.body.label = T("Body")
db.log.date.label = T("Date")
db.log.project.label = T("Project")
db.log.task.label = T("Task")
db.log.author.label = T("Author")
db.log.tags.label = T("Tags")
db.link.id.label = T("Id")
db.link.project.label = T("Project")
db.link.parent_table.label = T("Parent Table")
db.link.parent_id.label = T("Parent Id")
db.link.child_table.label = T("Child Table")
db.link.child_id.label = T("Child Id")
db.delphi.id.label = T("Id")
db.delphi.task.label = T("Task")
db.delphi.experts.label = T("Experts")
db.delphi.rounds.label = T("Rounds")
db.delphi.start.label = T("Start")
db.delphi.days.label = T("(window) days")
db.delphi.hours.label = T("(window) hours")
db.delphi.minutes.label = T("(window) minutes")
db.delphi.window.label = T("Window")
db.delphi.estimated.label = T("Estimated (hours)")
db.estimation.id.label = T("Id")
db.estimation.task.label = T("Task")
db.estimation.round.label = T("Round")
db.estimation.months.label = T("Months")
db.estimation.days.label = T("Days")
db.estimation.hours.label = T("Hours")
db.estimation.minutes.label = T("Minutes")
db.estimation.estimated.label = T("Estimated (hours)")
db.estimation.expert.label = T("Expert")
db.budget.id.label = T("Id")
db.budget.project.label = T("Project")
db.budget.author.label = T("Author")
db.budget.entry.label = T("Entry")
db.budget.description.label = T("Description")
db.budget.cathegory.label = T("Cathegory")
db.budget.start.label = T("Start")
db.budget.finish.label = T("Finish")
db.budget.quantity.label = T("Quantity")
db.budget.unit.label = T("Unit")
db.budget.amount.label = T("Amount")
db.delphi.days.label = T("(window) days")
db.delphi.hours.label = T("(window) hours")
db.delphi.minutes.label = T("(window) minutes")