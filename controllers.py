"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""

from yatl.helpers import A

from py4web import URL, abort, action, redirect, request

from .common import (
    T,
    auth,
    authenticated,
    cache,
    db,
    flash,
    logger,
    session,
    unauthenticated,
)

# custom imports
from py4web.utils.form import Form
from py4web import Field
from pydal.validators import (IS_EMAIL, IS_IN_SET, IS_IN_DB,
IS_NOT_EMPTY, IS_INT_IN_RANGE, IS_FLOAT_IN_RANGE, IS_EMPTY_OR)
from py4web.utils.grid import *
import datetime
import math
from apps.proyectero.models import (task_stage_format,
                                    estimated_compute)
import statistics

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
                 "link": T("Link tasks"),
                 "budget": T("Project budget")}

@action("index")
@action.uses("index.html", auth, T)
def index():
    # Landing page and project dashboard
    # Shows general project data
    # Has access to different actions for the current project
    # Both for admins and team

    message = T("You must be logged-in to view the dashboard")
    user = auth.get_user()
    as_admin = as_team = elapsed = team = admins = phases = \
        stages = tasks = project = None

    if user:
        message = None
        as_admin = db(db.project.admins.contains(auth.user_id)).select(db.project.id, db.project.name)
        as_team = db(db.project.team.contains(auth.user_id)).select(db.project.id, db.project.name)

    if session.project:
        project = db(db.project.id==session.project).select().first()
    
        # some data of interest
        if project.start:
            elapsed = datetime.datetime.now() - project.start
        team = db(db.auth_user.id.belongs(project.team or [])).select()
        admins = db(db.auth_user.id.belongs(project.admins or [])).select()
        phases = db(db.phase.project==project.id).select()
        stages = db(db.stage.phase.belongs([phase.id for phase in phases])).select()
        tasks = db(db.task.stage.belongs([stage.id for stage in stages])).select()

    # also should notify if there are delphi sessions open

    # maybe this could also show the last log entries

    return dict(project=project, elapsed=elapsed, team=team,
                admins=admins, phases=phases, stages=stages,
                tasks=tasks, as_admin=as_admin, message=message,
                as_team=as_team, session=session, user=user,
                team_actions=TEAM_ACTIONS,
                admin_actions=ADMIN_ACTIONS,
                T=T)

@action("project_create")
@action.uses("form.html", auth.user, T)
def project_create():
    db.project.admins.writable = False
    db.project.admins.readable = False
    db.project.team.writable = False
    db.project.team.readable = False
    db.project.admins.default = [auth.user_id,]

    form = Form(db.project)

    if form.accepted:
        flash.set(T("Project created"))
        redirect(URL("index"))
    return dict(form=form, T=T)

@action("project_select/<project:int>")
@action.uses("generic.html", auth.user, T)
def project_select(project):
    session.project = project
    flash.set(T("Project selected"))
    redirect(URL("index"))

@action("project_edit")
@action.uses("form.html", auth.user, T)
def project_edit():
    project = db(db.project.id==session.project).select().first()
    if not auth.user_id in (project.admins or []):
        flash.set(T("You need admin privileges to update project properties"))
        redirect(URL("index"))
    else:
        db.project.budget.writable = db.project.progress.writable = \
        db.project.admins.writable = db.project.team.writable = \
        db.project.budget.writable = db.project.progress.writable = False
        form = Form(db.project, project.id)
        if form.accepted:
            flash.set(T("Updated project properties"))
            redirect(URL("index"))
    return dict(form=form, T=T)

@action("admins_add")
@action.uses("form.html", auth.user, T)
def admins_add():
    project = db(db.project.id == session.project).select().first()
    if project.admins == None:
        project.admins = list()
    if auth.user_id in (project.admins or []):
        field = Field("users", "text")
        field.comment = T('Type a list of user emails separated by ";"')
        field.label = T("Add admin users to %s") % project.name
        form = Form([field,]) # custom form with textarea for adding users by mail
        if form.accepted:
            # create a list with emails entered
            # checking they are well-formed
            emails = []
            for item in str(form.vars["users"]).split(";"):
                if IS_EMAIL()(item)[1] is None:
                    emails.append(item)
            # query the users in the system that match
            users = db(db.auth_user.email.belongs(emails)).select()
            # make any user retrieved project admin
            # do not add duplicated
            count = 0
            for user in users:
                if not user.id in (project.admins or []):
                    project.admins.append(user.id)
                    count += 1
            if count > 0:
                flash.set(T("%s users added") % count)
                project.update_record()                
            else:
                flash.set(T("No users added"))
            redirect(URL("index"))
    else:
        flash.set(T("You need project admin rights for this action"))
        redirect(URL("index"))
    return dict(form=form, T=T)

@action("team_add")
@action.uses("form.html", auth.user, T)
def team_add():
    project = db(db.project.id == session.project).select().first()
    if project.team == None:
        project.team = list()    
    if auth.user_id in (project.admins or []):
        field = Field("users", "text")
        field.comment = T('Type a list of user emails separated by ";"')
        field.label = T("Add team users to %s") % project.name
        form = Form([field,]) # custom form with textarea for adding users by mail
        if form.accepted:
            # create a list with emails entered
            # checking they are well-formed
            emails = []
            for item in str(form.vars["users"]).split(";"):
                if IS_EMAIL()(item)[1] is None:
                    emails.append(item)
            # query the users in the system that match
            users = db(db.auth_user.email.belongs(emails)).select()
            # make any user retrieved project admin
            # do not add duplicated
            count = 0
            for user in users:
                if not user.id in (project.team or []):
                    project.team.append(user.id)
                    count += 1
            if count > 0:
                flash.set(T("%s users added") % count)
                project.update_record()                
            else:
                flash.set(T("No users added"))
            redirect(URL("index"))
    else:
        flash.set(T("You need project admin rights for this action"))
        redirect(URL("index"))
    return dict(form=form, T=T)


@action("admins_remove")
@action.uses("form.html", auth.user, T)
def admins_remove():
    project = db(db.project.id == session.project).select().first()
    if project.admins == None:
        project.admins = list()    
    if auth.user_id in (project.admins or []):
        field = Field("users", "text")
        field.comment = T('Type a list of user emails separated by ";"')
        field.label = T("Remove admin users from %s") % project.name
        form = Form([field,]) # custom form with textarea for adding users by mail
        if form.accepted:
            # create a list with emails entered
            # checking they are well-formed
            emails = []
            for item in str(form.vars["users"]).split(";"):
                if IS_EMAIL()(item)[1] is None:
                    emails.append(item)
            # query the users in the system that match
            users = db(db.auth_user.email.belongs(emails)).select()
            # make any user retrieved project admin
            # do not add duplicated
            count = 0
            for user in users:
                if user.id in (project.admins or []):
                    project.admins.pop(project.admins.index(user.id))
                    count += 1
            if count > 0:
                flash.set(T("%s admins removed") % count)
                project.update_record()                
            else:
                flash.set(T("No admins removed"))
                redirect(URL("index"))
    else:
        flash.set(T("You need project admin rights for this action")) # forbidden
        redirect(URL("index"))
    return dict(form=form, T=T)

@action("team_remove")
@action.uses("form.html", auth.user, T)
def team_remove():
    project = db(db.project.id == session.project).select().first()
    if project.team == None:
        project.team = list()    
    if auth.user_id in (project.admins or []):
        field = Field("users", "text")
        field.comment = T('Type a list of user emails separated by ";"')
        field.label = T("Remove team users from %s") % project.name
        form = Form([field,]) # custom form with textarea for adding users by mail
        if form.accepted:
            # create a list with emails entered
            # checking they are well-formed
            emails = []
            for item in str(form.vars["users"]).split(";"):
                if IS_EMAIL()(item)[1] is None:
                    emails.append(item)
            # query the users in the system that match
            users = db(db.auth_user.email.belongs(emails)).select()
            # make any user retrieved project admin
            # do not add duplicated
            count = 0
            for user in users:
                if user.id in (project.team or []):
                    project.team.pop(project.team.index(user.id))
                    count += 1
            if count > 0:
                flash.set(T("%s team members removed") % count)
                project.update_record()
            else:
                flash.set(T("No team members removed"))
            redirect(URL("index"))                
    else:
        flash.set(T("You need project admin rights for this action")) # forbidden
        redirect(URL("index"))
    return dict(form=form, T=T)

@action("phases")
@action.uses("grid.html", auth.user, T)
def phases():
    if session.project:
        project = db(db.project.id == session.project).select().first()
        if auth.user_id in (project.admins or []):
            db.phase.project.default = session.project
            db.phase.project.writable = False
            grid = Grid(query=db.phase.project==project.id, T=T)
            return dict(grid=grid, T=T)
        else:
            flash.set(T("You need project admin rights for managing phases"))
            redirect(URL("index"))
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

@action("stages")
@action.uses("grid.html", auth.user, T)
def stages():
    if session.project:
        project = db(db.project.id == session.project).select().first()
        phases = db(db.phase.project == project.id).select()
        phase_list = [phase.id for phase in phases]
        if auth.user_id in (project.admins or []):
            grid = Grid(query=db.stage.phase.belongs(phase_list), T=T)
            return dict(grid=grid, T=T)
        else:
            flash.set(T("You need project admin rights for managing stages"))
            redirect(URL("index"))
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

@action("tasks")
@action.uses("grid.html", auth.user, T)
def tasks():
    if session.project:
        project = db(db.project.id == session.project).select().first()
        is_admin = auth.user_id in (project.admins or [])
        is_team = auth.user_id in (project.team or [])
        phases = db(db.phase.project == project.id).select()
        phase_list = [phase.id for phase in phases]
        if (type(project.team) == list) and (len(project.team) > 0):
            team_set = db(db.auth_user.id.belongs(project.team))
            db.task.team.requires = [IS_NOT_EMPTY(),
                IS_IN_DB(team_set,
                         db.auth_user.id,
                         db.auth_user._format,
                         multiple=True)]
        else:
            db.task.team.writable = False
            db.task.team.comment = T("You must choose a team for the project before asigning the task")
        if is_admin or is_team:
            columns = [db.task.id, db.task.name, db.task.tags,
                       db.task.stage, db.task.status,
                       db.task.team,
                       Column(T("Progress"), lambda row: A(T("Report"),
                              _href=URL("progress/%d" % row.id)) \
                                if auth.user_id in (row.team or [])\
                                else "-"),
                       db.task.start, db.task.estimated]

            stage_set = db(db.stage.phase.belongs(phase_list))
            db.task.stage.requires = [IS_NOT_EMPTY(),
               IS_IN_DB(stage_set,
                        db.stage.id,
                        task_stage_format)]
            stage_list = [row.id for row in stage_set.select()]
            grid = Grid(query=db.task.stage.belongs(stage_list),
                        columns=columns,
                        create=is_admin,
                        editable=is_admin,
                        deletable=is_admin, T=T)
            return dict(grid=grid, T=T)
        else:
            flash.set(T("You need project rights for managing tasks"))
            redirect(URL("index"))
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

@action("links")
@action.uses("links.html", auth.user, T)
def links():
    if session.project:
        project = db(db.project.id == session.project).select().first()
        if auth.user_id in (project.admins or []):
            # db.link.parent_table.readable = False
            grid = Grid(query=db.link.project==project.id,
                        create=False,
                        editable=False, T=T)
            return dict(new_link=A(T("Add link"),
                                   _href=URL("link")),
                        grid=grid, T=T)
        else:
            flash.set(T("You need project admin rights for managing links"))
            redirect(URL("index"))
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

@action("link")
@action.uses("form.html", auth.user, T)
def link():
    if session.project:
        project = db(db.project.id == session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    if not auth.user_id in (project.admins or []):
        flash.set(T("Only admins can link tasks"))
        redirect(URL("index"))

    # retrieve all phases from project
    phases = db(db.phase.project == project.id).select().as_dict()
    # retrieve all stages from phases
    stages = db(db.stage.phase.belongs(phases.keys())).select().as_dict()
    # retrieve all tasks from stages
    tasks = db(db.task.stage.belongs(stages.keys())).select().as_dict()
    # build the option set (any of the above)
    options = dict()
    for k, v in phases.items():
        options["phase_%d" % k] = v["label"] or v["name"]
    for k, v in stages.items():
        options["stage_%d" % k] = "%s - %s" % (
        phases[v["phase"]]["label"] or phases[v["phase"]]["name"],
        v["label"] or v["name"])
    for k, v in tasks.items():
        stage = stages[v["stage"]]
        phase = phases[stage["phase"]]
        options["task_%d" % k] = "%s - %s - %s" % (
        phase["label"] or phase["name"],
        stage["label"] or stage["name"],
        v["label"] or v["name"])

    parent = Field("parent")
    parent.requires = IS_IN_SET(options)
    parent.label = T("Link from parent")
    child = Field("child")
    child.requires = IS_IN_SET(options)
    child.label = T("Link to child")
    form = Form([parent, child])

    if form.accepted:
        # a node cannot link to himself
        if form.vars["parent"] == form.vars["child"]:
            flash.set(T("Both fields cannot be the same node!"))
        else:
            # you cannot link again two nodes
            # (no matter inwhich way) retrieve current links and
            # search for matching pair in case
            # there is a duplicate
            duplicate = False
            for row in db(db.link.project == project.id).select():
                checktuple = ("%s_%d" % (row.parent_table,
                                         row.parent_id),
                              "%s_%d" % (row.child_table,
                                         row.child_id))
                if (form.vars["parent"] in checktuple) and \
                    (form.vars["child"] in checktuple):
                    flash.set("The link already exists!")
                    duplicate = True
            # In case there are no duplicates,
            # go ahead with db record
            if not duplicate:
                parent_tuple = form.vars["parent"].split("_")
                child_tuple = form.vars["child"].split("_")
                link_id = db.link.insert(
                    project = project.id,
                    parent_table=parent_tuple[0],
                    parent_id=int(parent_tuple[1]),
                    child_table=child_tuple[0],
                    child_id=int(child_tuple[1]))
                flash.set(T("Link stored with record id #%d") % link_id)
                redirect(URL("links"))
    return dict(form=form, T=T)

@action("delphi/<task_id:int>")
@action.uses("form.html", auth.user, T)
def delphi(task_id):
    # Project time wideband-delphi estimation
    # Here an admin can setup the process

    # check if user is project admin
    project = db(db.project.id == session.project).select().first()
    task = db(db.task.id == task_id).select().first()
    stage = db(db.stage.id == task.stage).select().first()
    phase = db(db.phase.id == stage.phase).select().first()
    delphi = db(db.delphi.task == task_id).select().first()

    db.delphi.task.default = task_id
    db.delphi.task.writable = False
    db.delphi.start.writable = False
    db.delphi.estimated.readable = False
    db.delphi.estimated.writable = False
    db.delphi.window.readable = False
    db.delphi.window.writable = False

    if not (project.id == phase.project):
        flash.set(T("The task you chose does not belong to the current project"))
        redirect(URL("index"))
    elif not (auth.user_id in (project.admins or [])):
        flash.set(T("You must have project admin rights for this action"))
        redirect(URL("index"))
    elif project.team in (None, []):
        flash.set(T("Your project has no team members"))
        redirect(URL("index"))
    # check if there is a delphi process already stored
    # if there is no record, return a form
    elif not delphi:
        # filter project team as possible task experts
        team_set = db(db.auth_user.id.belongs(project.team))
        db.delphi.experts.requires = [IS_NOT_EMPTY(),
            IS_IN_DB(team_set,
                    db.auth_user.id,
                    db.auth_user._format,
                    multiple=True)]
    
        db.delphi.start.default = datetime.datetime.now()
        
        form = Form(db.delphi)
    # otherwise, show record data and allow session
    # abort (and only that)
    else:
        db.delphi.experts.writable = False
        db.delphi.rounds.writable = False
        db.delphi.days.writable = False
        db.delphi.hours.writable = False
        db.delphi.minutes.writable = False
        form = Form(db.delphi, delphi.id)

    if form.accepted:
        if form.record == None:
            flash.set(T("New delphi estimation started"))
        elif form.deleted:
            db(db.estimation.task==task_id).delete()
            flash.set(T("Delphi session and related estimations deleted"))
        else:
            # Edit submission without delete option check
            # BUG: the action does not update the window field
            db.rollback()
        redirect(URL("delphi_panel"))
    return dict(form=form, T=T)

@action("estimate/<task_id:int>")
@action.uses("estimate.html", auth.user, T)
def estimate(task_id):
    # get the delphi record
    delphi = db(db.delphi.task == task_id).select().first()
    if not delphi:
        flash.set(T("No delphi session configured for this task"))
        redirect(URL("index"))
    # check that the user has team rights
    elif not auth.user_id in (delphi.experts or ()):
        flash.set(T("You do not belong to the estimation team"))
        redirect(URL("index"))        
    else:
        # test for which round the team is at
        elapsed_delta = datetime.datetime.now() -delphi.start
        window_delta = datetime.timedelta(hours=delphi.window)

        rounds_elapsed = (elapsed_delta.total_seconds()/window_delta.total_seconds()) +1
        rounds_theoretical = int(rounds_elapsed)
        # in case the delphi is old, exit and notify the user
        if rounds_theoretical > delphi.rounds:
            flash.set(T("The estimation session for this task is over"))
            redirect(URL("index"))
        else:
            rounds_current = rounds_theoretical

        remaining_window = (1- (rounds_elapsed % 1))*window_delta

        # check if the user has an entry for this round
        query = db.estimation.task == task_id
        query &= db.estimation.expert == auth.user_id
        query &= db.estimation.round == rounds_current
        estimation = db(query).select().first()

        # If not the first round,
        # collect estimations from previous one
        maximum = None
        if rounds_current > 1:
            query = db.estimation.task == task_id
            query &= db.estimation.round == rounds_current -1
            previous = [row.estimated for row in db(query).select()]

            # and calculate the round upper boundary
            if len(previous) > 0:
                previous_mean = statistics.mean(previous)
                # the threshold ought to be user defined
                threshold = previous_mean * 1.17
                maximum = datetime.timedelta(hours=threshold)

                # Warn about the threshold in hours
                db.estimation.round.comment = \
                T("Estimation must not exceed %f hours") % (maximum.total_seconds()/3600)

        # retrieve de task record to visualize it
        task = db(db.task.id == task_id).select().first()

        if not estimation:
            db.estimation.expert.default = auth.user_id
            db.estimation.task.default = task_id
            db.estimation.round.default = rounds_current

            form = Form(db.estimation, dbio=False)
            if form.accepted:
                # convert submitted values to timedelta
                computed = datetime.timedelta(hours=estimated_compute(form.vars))

                if db.estimation.round.default < rounds_theoretical:
                    flash.set(T("Hold on... The time for this round is up!"))
                    redirect(URL("delphi_panel"))
                elif (maximum != None) and (computed > maximum):
                    flash.set(T("Estimation is beyond the maximum"))
                    redirect(URL("estimate/%s" % task_id))
                else:
                    # register estimation
                    db.estimation.insert(**form.vars)
                    flash.set(T("Estimation submitted"))
                    redirect(URL("delphi_panel"))
        else:
            # There is an estimation for this round already,
            # so just show the contents
            form = Form(db.estimation, estimation.id, readonly=True)
        return dict(form=form, maximum=maximum,
                    remaining_window=remaining_window, task=task, T=T)

@action("estimations")
@action.uses("grid.html", auth.user, T)
def estimations():
    # A grid of estimations for project admins
    project = db(db.project.id==session.project).select().first()
    is_admin = auth.user_id in (project.admins or [])
    if not is_admin:
        flash.set("Only for admins")
        redirect(URL("delphi_panel"))
    phases = db(db.phase.project==project.id).select()
    stages = db(db.stage.phase.belongs([phase.id for phase in phases])).select()
    tasks = db(db.task.stage.belongs([stage.id for stage in stages])).select()
    query = db.estimation.task.belongs([task.id for task in tasks])
    db.estimation.expert.readable=False
    grid = Grid(query=query, create=False, editable=False, deletable=False, T=T)
    return dict(grid=grid, T=T)

@action("budget")
@action.uses("budget.html", auth.user, T)
def budget():
    if not session.project:
        flash.set(T("Choose a project first"))
        redirect(URL("index"))
    else:
        project = db(db.project.id == session.project).select().first()
        db.budget.author.default = auth.user_id
        db.budget.project.default = project.id

        # Calculate the total budget
        budget_set = db(db.budget.project == project.id).select()
        total = sum([row.amount for row in budget_set])
        grid = Grid(query=db.budget.project==project.id, T=T)
    return dict(grid=grid, total=total, T=T)

@action("gantt")
@action.uses("gantt.html", auth.user, T)
def gantt():
    if not session.project:
        flash.set("Choose a project first")
        redirect(URL("index"))
    else:
        project = db(db.project.id == session.project).select().first()

    phases = db(db.phase.project == project.id).select().as_dict()
    stages = db(db.stage.phase.belongs(k for k in phases)).select().as_dict()
    tasks = db(db.task.stage.belongs(k for k in stages)).select()

    items = list()
    for task in tasks:
        # check if the task has a start time
        if task.start and (not task.estimated == None):
            id = task.id
            start = task.start
            name = task.label or task.name
            delta = datetime.timedelta(hours=task.estimated)
            end = task.start + delta
            # just use a conventional progress value
            if task.status == "done":
                progress = 100.0
            elif task.status == "in_progress":
                progress = 50.0
            else:
                progress = 0.0
            items.append(dict(id=id, start=start, name=name, end=end,
                progress=progress))
    return dict(items=items, T=T)

@action("cpm")
@action.uses("cpm.html", auth.user, T)
def cpm():
    # - populate and process the project data
    # in a proper format for cytoscape
    # - also identify the critical path nodes
    # - and handle different kinds of relations
    # between nodes, phases and stages
    
    # on different kinds of relations, any linked
    # type of project element should be returned
    # as a task for a simpler build process
    # stage and phase nodes should have a 0
    # duration, the same as start and finish

    # TODO: this is got to be refactored!
    # too much loops, too much objects

    # import CPM calculations library (by Valdecy)
    from pyCritical.src import critical_path_method

    # import a DAG sort class (that uses DSF)
    from apps.proyectero.dagsort import Graph

    if not session.project:
        flash.set(T("Choose a project first"))
        redirect(URL("index"))
    else:
        project = db(db.project.id == session.project).select().first()

    phases = db(db.phase.project == project.id).select().as_dict()
    stages = db(db.stage.phase.belongs(k for k in phases)).select().as_dict()
    tasks = db(db.task.stage.belongs(k for k in stages)).select().as_dict()
    links = db(db.link.project == project.id).select()

    # all records retrieved but classified by kind of entity
    records = dict(phase=phases, stage=stages, task=tasks)

    # an object to pre-populate each node and its dependencies
    nodes = dict()

    # loop trough the links and populate each node data
    for row in links:
        # pyCritical requires us to provide a key for each node
        child_key = "%s_%d" % (row.child_table, row.child_id)
        parent_key = "%s_%d" % (row.parent_table, row.parent_id)

        # if there are broken links (deleted nodes), skip them
        child_exists = row.child_id in records[row.child_table]
        parent_exists = row.parent_id in records[row.parent_table]
        if not (child_exists and parent_exists):
            continue

        for key in (child_key, parent_key):
            if key == parent_key:
                record_id = row.parent_id
            else:
                record_id = row.child_id

            # some logical spaghetti to recover the entity db record
            if not key in nodes:
                nodes[key] = dict(duration=0.0, dependencies=list())
                # if this is a task, get the duration                
                if "task" in key:
                    record = records["task"][record_id]
                    nodes[key]["duration"] = record["estimated"]
                elif "stage" in key:
                    record = records["stage"][record_id]
                else:
                    record = records["phase"][record_id]

                # we need to store also the name of the CPM node
                nodes[key]["label"] = record["label"] or record["name"]

        # add the parent to the child's list of dependecies
        nodes[child_key]["dependencies"].append(parent_key)

    # now we have to populate the dataset
    dataset = []

    for k, v in nodes.items():
        dataset.append([k, v["dependencies"], v["duration"]])

    # In case there is not enough information
    # stop processing the view
    if not dataset:
        flash.set(T("No data to build the graph"))
        redirect(URL("index"))

    # process the cpm and get the results
    cpm = critical_path_method(dataset).to_dict()

    # for cleaner client processing, add the results to
    # the nodes and edges

    # the DAG sort by DFS object
    dagsort = Graph(len(nodes))
    indexes = dict()
    counter = 0

    for n in nodes:
        node = nodes[n]
        node["ES"] = cpm["ES"][n]
        node["EF"] = cpm["EF"][n]
        node["LS"] = cpm["LS"][n]
        node["LF"] = cpm["LF"][n]
        node["Slack"] = cpm["Slack"][n]
        if cpm["Slack"][n] == 0:
            node["Critical"] = True
        else:
            node["Critical"] = False
        # dag sorter data
        indexes[n] = counter
        counter += 1

    for n in nodes:
        for m in nodes[n]["dependencies"]:
            dagsort.add_edge(indexes[n], indexes[m])

    ordered = dagsort.topological_sort()
    reordered = list(reversed(ordered))
    indexes_swapped = {v: k for k, v in indexes.items()}

    # return the cytoscape data and other stuff
    return dict(nodes=nodes, ordered=reordered,
                indexes=indexes_swapped, T=T)

@action("delphi_update")
@action.uses("generic.html", auth.user, T)
def delphi_update():
    # this action should:
    # - get the session project

    project = db(db.project.id==session.project).select().first()

    if not project:
        flash.set(T("Choose a project first"))
        redirect(URL("index"))

    if not(auth.user_id in (project.admins or [])):
        flash.set(T("Only admins can update delphi"))
        redirect(URL("index"))

    # - retrieve any delphi session finished
    # that has no estimation calculated
    phases = db(db.phase.project == project.id).select()
    phase_ids = [phase.id for phase in phases]
    stages = db(db.stage.phase.belongs(phase_ids)).select()
    stage_ids = [stage.id for stage in stages]
    tasks = db(db.task.stage.belongs(stage_ids)).select()
    task_ids = [task.id for task in tasks]

    now = datetime.datetime.now()

    delphies_set = db.delphi.task.belongs(task_ids)
    delphies_set &= db.delphi.estimated == None
    delphies = db(delphies_set).select()

    counter = 0
    for delphi in delphies:
        # check if the delphi session is finished
        window = datetime.timedelta(hours=delphi.window)
        deadline = delphi.start + (delphi.rounds*window)
        estimated = None

        if now > deadline:
            # delphi time is up
            # get any estimation for any round
            estimations_query = (db.estimation.task==delphi.task) & \
                (db.estimation.estimated != None)
            estimations = db(estimations_query).select().as_dict()

            # and set the delphi estimation per round
            # preserving the last round with actual estimations
            for round in range(delphi.rounds):
                actual_round = round +1
                values = []
                for key in estimations:
                    if estimations[key]["round"] == actual_round:
                        values.append(estimations[key]["estimated"])
                if len(values) > 0:
                    estimated = statistics.mean(values)

            if not (estimated == None):
                delphi.update_record(estimated=estimated)
                db(db.task.id==delphi.task).update(estimated=estimated)
                counter += 1
            else:
                # TODO: remove delphi and linked records
                # since deadline is over and there are no
                # estimations
                pass

    # return a message notifying the results
    if counter > 0:
        flash.set(T("%s task estimations updated") % counter)
    else:
        flash.set(T("No task estimations updated"))
    redirect(URL("delphi_panel"))

@action("s_curve")
@action.uses("s_curve.html", auth.user, T)
def s_curve():
    # this action should:
    # - get the session project
    # - retrieve all tasks for the project
    # - retriene all progress reports for the tasks
    # - build a table acording to the gap established with:
    #   - columns for each date step
    #   - a row for the progress based on the task estimation
    #   - a row for the actual progress based on the progress records
    # return the table to be processed by a client-side software
    # see reference for building an s-curve
    # https://www.projectcontrolacademy.com/common-uses-of-s-curves/

    if session.project:
        project = db(db.project.id==session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    # Check if the project start time is set
    # and if not, redirect with a warning
    if not project.start:
        flash.set(T("Set a project start time before checking advance"))
        redirect(URL("index"))

    # set projected and actual curve data objects
    projected = dict()
    projected_data = dict()
    actual = dict()
    actual_data = dict()
    # objects used for js graph tool
    labels = list()
    projected_dataset = list()
    actual_dataset = list()

    # get any project data from db
    phases = db(db.phase.project==project.id).select().as_dict()
    phase_ids = [phase for phase in phases]
    stages = db(db.stage.phase.belongs(phase_ids)).select().as_dict()
    stage_ids = [stage for stage in stages]
    tasks = db(db.task.stage.belongs(stage_ids)).select().as_dict()
    task_ids = [task for task in tasks]
    project_end = project.start
    estimated_total = 0.0

    # set task estimated bounds
    for task in tasks:
        start = tasks[task]["start"] or project.start
        estimated = tasks[task]["estimated"] or 0.0
        delta = datetime.timedelta(hours=estimated)
        estimated_total += estimated
        estimated_end = start + delta
        tasks[task]["estimated_end"] = estimated_end
        # update project upper bounds
        if estimated_end > project_end:
            project_end = estimated_end

    # computed deadline for updating the project record
    deadline = project_end
    deadline_string = "%04d-%02d-%02d" % (deadline.year, deadline.month, deadline.day)

    if estimated_total <= 0:
        flash.set(T("Project must extend in time to build the s-curve"))
        redirect(URL("index"))

    # ask the user for some options
    form = Form([Field("step",
                      requires=IS_IN_SET({"day": T("Days"),
                          "week": T("Weeks"), "month": T("Months")}),
                      default="week",
                      label=T("Choose a time rate")),
                Field("date_from", "datetime",
                      default=project.start,
                      comment=T("Defaults to project's start"),
                      label=T("From")),
                Field("date_to", "datetime",
                      default=project_end,
                      comment=T("Defaults to project's end"),
                      label=T("To"))])

    if form.accepted:
        # set the time boundaries
        start_day = datetime.date(year=form.vars["date_from"].year,
                                  month=form.vars["date_from"].month,
                                  day=form.vars["date_from"].day)
        end_day = datetime.date(year=form.vars["date_to"].year,
                                  month=form.vars["date_to"].month,
                                  day=form.vars["date_to"].day)

        # populate projected curve data
        for task in tasks:
            estimated_end = tasks[task]["estimated_end"]
            date = "%04d-%02d-%02d" % (estimated_end.year,
                                       estimated_end.month, estimated_end.day)
            estimated = tasks[task]["estimated"] or 0.0
            percent = (estimated/estimated_total)*100
            if not date in projected:
                projected[date] = percent
            else:
                projected[date] += percent 

        # populate actual curve data
        for task in tasks:
            if tasks[task]["status"] == "done":
                progress_increment = 100.0
                progress_date = tasks[task]["end"]
            else:
                progress_increment = 0.0
                progress_date = tasks[task]["start"]

            date = "%04d-%02d-%02d" % (progress_date.year,
                    progress_date.month, progress_date.day)
            task_estimated = tasks[task]["estimated"] or 0.0
            task_partial = (task_estimated/100)*progress_increment
            percent = (task_partial/estimated_total)*100

            if not date in actual:
                actual[date] = percent
            else:
                actual[date] += percent

        # update with sum for step
        for date in projected:
            projected_data[date] = acumulated(date, projected)

        for date in actual:
            actual_data[date] = acumulated(date, actual)

        # Now we need an ordered list of project days,
        # other for projected progress, and other for actual,
        # to configure chart.js data properly

        keepgoing = True
        day_delta = datetime.timedelta(days=1)
        current_day = start_day

        while (current_day <= end_day):
            add_data = False
            current_month = (current_day.year, current_day.month)
            current_day_string = "%04d-%02d-%02d" % (
                current_day.year,
                current_day.month,
                current_day.day)

            # week, day, month logic
            # labels.append(current_day_string)
            # projected_dataset.append(projected_dataset_value)
            # actual_dataset.append(actual_dataset_value)

            # for performance, this check should be
            # processed at top of the loop

            if form.vars["step"] == "day":
                add_data = True
            elif form.vars["step"] == "week":
                if not (current_day.weekday() == 0):
                    if current_day in (start_day, end_day):
                        add_data = True
                elif current_day.weekday() == 0:
                    add_data = True
                else:
                    pass
            else:
                # if this is the start day
                # or next day is next month's,
                # add this value to the dataset
                next_day = (current_day + day_delta)
                next_days_month = (next_day.year, next_day.month)

                if current_day in (start_day, end_day):
                    add_data = True
                elif (not add_data) and (next_days_month != current_month):
                    add_data = True
                else:
                    pass

            if add_data:
                if (current_day_string in projected_data):
                    projected_dataset_value = projected_data[current_day_string]
                else:
                    projected_dataset_value = acumulated_lookup(
                        current_day_string, projected_data)
                
                if (current_day_string in actual_data):
                    actual_dataset_value = actual_data[current_day_string]
                else:
                    # for actual_dataset make a lookup (auxiliar function)
                    # to get the better progress in case there is no value
                    # for that day                        
                    actual_dataset_value = acumulated_lookup(
                        current_day_string, actual_data)

                labels.append(current_day_string)
                projected_dataset.append(projected_dataset_value)
                actual_dataset.append(actual_dataset_value)
                if current_day_string == deadline_string:
                    # update deadline data to the project record
                    project.update_record(deadline=deadline,
                        progress=actual_dataset_value)

            current_day += day_delta

    return dict(form=form, labels=labels,
                projected=projected_dataset,
                actual=actual_dataset, T=T)

@action("kanban_board")
@action.uses("kanban_board.html", auth.user, T)
def kanban_board():
    # this action should:
    # get the session project
    # ask for a project stage with a form
    # get any task from stage
    # get any progress from tasks
    # separate tasks in those with:
    #     - progress = 0%
    #     - 0% < progress < 100%
    #     - progress >= 100%
    # build the board data to be processed
    # client-side somehow

    if session.project:
        project = db(db.project.id==session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    data = dict()

    phases = db(db.phase.project==project.id).select().as_dict()
    stages = db(db.stage.phase.belongs([phase for phase in phases])).select()
    options = dict()

    for stage in stages:
        phase = phases[stage.phase]
        phase_label = phase["label"] or phase["name"]
        stage_label = stage.label or stage.name
        options[stage.id] = "%s -> %s" % (phase_label, stage_label)

    form = Form([Field("stage", "integer", requires=IS_IN_SET(options),
                       label=T("Choose a stage")),])

    if form.accepted:
        tasks = db(db.task.stage==form.vars["stage"]).select().as_dict()
        for task in tasks:
            if tasks[task]["status"] == "done":
                progress = 100.0
            elif tasks[task]["status"] == "in_progress":
                progress = 1.0
            else:
                progress = 0.0
            data[task] = dict(progress=progress, id=task,
                              label=tasks[task]["label"] or tasks[task]["name"])
    return dict(form=form, data=data, T=T)


@action("log")
@action.uses("grid.html", auth.user, T)
def log():
    # returns a grid of task progress
    if session.project:
        project = db(db.project.id==session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    phase_set = db(db.phase.project==project.id)
    phase_ids = [phase.id for phase in phase_set.select()]
    stage_set = db(db.stage.phase.belongs(phase_ids))
    stage_ids = [phase.id for phase in phase_set.select()]
    task_set = db(db.task.stage.belongs(
        stage_ids))

    # log rules
    db.log.project.default = project.id
    db.log.project.writable = False
    db.log.author.default = auth.user_id
    db.log.author.writable = False
    db.log.date.default = datetime.datetime.now()
    db.log.date.writable = False
    change_log = auth.user_id in (project.admins or [])

    log_task_query = db.task.id.belongs(stage_ids)
    if not (auth.user_id in (project.admins or [])):
        log_task_query &= db.task.team.contains(auth.user_id)

    log_task_set = db(log_task_query)

    db.log.task.requires = IS_EMPTY_OR(IS_IN_DB(log_task_set,
                                     db.task.id,
                                     db.task._format))

    grid = Grid(query=db.log.project==project.id,
                  create=True, editable=change_log,
                  deletable=change_log, T=T)

    return dict(grid=grid, T=T)

@action("delphi_panel")
@action.uses("delphi_panel.html", auth.user, T)
def delphi_panel():
    # build delphi data object with related task,
    # session time remaining, current round, current round time remaining
    # also a round completed check column (for team)

    # the view should check if user can estimate (is expert) and if so,
    # add a link to estimation

    if session.project:
        project = db(db.project.id==session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    is_admin = auth.user_id in (project.admins or [])
    is_team = auth.user_id in (project.team or [])

    if not (is_team or is_admin):
        flash.set("You have no rights on this project")
        redirect(URL("index"))

    phases = db(db.phase.project==project.id).select()
    stages = db(db.stage.phase.belongs([phase.id for phase in phases])).select()
    tasks = db(db.task.stage.belongs([stage.id for stage in stages])).select()
    task_data = tasks.as_dict()

    delphi_query = db.delphi.estimated == None
    task_ids = [task.id for task in tasks]
    delphi_query &= db.delphi.task.belongs(task_ids)

    delphi_sessions = db(delphi_query).select()
    estimations_query = db.estimation.task.belongs(task_ids)
    estimation_data = db(estimations_query).select().as_dict()

    now = datetime.datetime.now()

    delphi_data = dict()

    # List those tasks which have delphi sessions
    delphi_tasks = list()

    # Retrieve delphi related data for each entry
    for ds in delphi_sessions:
        delphi_tasks.append(ds.task)
        delphi_data[ds.id] = dict(task=ds.task,
                                  expert=False, finished=False,
                                  round=None, rounds=ds.rounds,
                                  remaining=None,
                                  completed=False, estimations=0,
                                  experts=len(ds.experts or []))
        
        # - if user is expert for this delphi        
        if auth.user_id in (ds.experts or []):
            delphi_data[ds.id]["expert"] = True

        # - which is the current round (or finished)
        elapsed = now - ds.start
        window = datetime.timedelta(hours=ds.window)
        delphi_data[ds.id]["round"] = int(elapsed/window +1)

        if delphi_data[ds.id]["round"] > ds.rounds:
            delphi_data[ds.id]["finished"] = True
        else:
            # - round deadline (if not finished)            
            deadline = ds.start + window*(delphi_data[ds.id]["round"])
            delphi_data[ds.id]["remaining"] = deadline - now

            # - count round estimations completed from the total of experts
            # - check also if user has completed this round
            for estimation in estimation_data:
                if estimation_data[estimation]["task"] == ds.task:
                    if estimation_data[estimation]["round"] == delphi_data[ds.id]["round"]:
                        delphi_data[ds.id]["estimations"] += 1
                        if estimation_data[estimation]["expert"] == auth.user_id:
                            delphi_data[ds.id]["completed"] = True

    return dict(project=project,
                phases_data=phases.as_dict(),
                stages_data=stages.as_dict(),
                estimation_data=estimation_data,
                delphi_data=delphi_data,
                task_data=task_data,
                is_admin=is_admin,
                is_team=is_team,
                delphi_tasks=delphi_tasks, T=T)

@action("progress/<task_id:int>")
@action.uses("form.html", auth.user, T)
def progress(task_id):
    # Check there is an active project
    if session.project:
        project = db(db.project.id==session.project).select().first()
    else:
        flash.set(T("No project selected"))
        redirect(URL("index"))

    task = db(db.task.id==task_id).select().first()

    now = datetime.datetime.now()

    # Also check user rights
    is_admin = auth.user_id in (project.admins or [])
    is_assigned = auth.user_id in task.team

    if not (is_admin or is_assigned):
        flash.set("No user rights on this task")
        redirect(URL("tasks"))

    # Restrict fields for different roles
    db.task.status.default = task.status or "pending"
    db.log.title.comment = T("Name the task report")
    db.log.body.comment = T("Write some comment on the progress")
    # Possibly DAL does not support microsencods in datetime
    db.task.end.default = now.replace(microsecond=0)
    db.task.end.comment=T("Only applies for done status; defaults to current time")

    # Autopopulate form with task status and other stuff

    form = Form([db.task.status,
                db.task.end,
                db.log.title,
                db.log.body,
                db.log.tags])
    
    # On form accept, make changes if neccesary,
    # update the task and add the log
    if form.accepted:
        if (form.vars["status"]) == "done" and (
            not task.status == "done"):
            end = form.vars["end"] or now
        else:
            end = task.end

        task.update_record(status=form.vars["status"],
                              end=end)
        db.log.insert(
            author=auth.user_id,
            title=form.vars["title"],
            body=form.vars["body"],
            task=task.id,
            date=datetime.datetime.now(),
            project=project.id,
            tags=form.vars["tags"])
        flash.set(T("New status update recorded"))
        redirect(URL("tasks"))
    return dict(form=form, T=T)

# auxiliar function of s_curve
# returns the sum of anything in obj before or as to date
def acumulated(date, obj):
    total = 0.0
    for key in obj:
        if key <= date:
            total += obj[key]
    return total

# auxiliar function to search for the better
# progress state before a date
# for s_curve
def acumulated_lookup(date, obj):
    value = 0.0
    for k in obj:
        if ((k < date) and (obj[k] > value)):
            value = obj[k]
    return value


