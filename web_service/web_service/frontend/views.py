from flask import Blueprint, Flask, jsonify, request, render_template
from web_service.helpers import helpers
from pdb import set_trace as bp
import logging
import traceback

frontend_blueprint = Blueprint(
    'frontend',
    __name__,
    template_folder='../templates')

app = Flask(__name__)


@frontend_blueprint.before_app_first_request
def setup():
    helpers.onetime_setup_required()


@frontend_blueprint.route('/', methods=['GET'])
@frontend_blueprint.route('/frontend/', methods=['GET'])
def index():
    return render_template('index.html')


@frontend_blueprint.route('/frontend/dashboard', methods=['GET'])
def dashboard():
    try:
        services = helpers.get_services()
        pipelines = helpers.get_pipelines_for_dashboard()
        workspaces = helpers.get_workspaces()

    except Exception as e:
        services = []
        pipelines = []
        workspaces = []
        logging.error(
            "Unable to retrieve Build@Scale dashboard data: %s" % traceback.format_exc())
    return render_template('dashboard.html', services=services, pipelines=pipelines, workspaces=workspaces)


@frontend_blueprint.route('/frontend/pipeline/create', methods=['GET'])
def create_project():
    try:
        config_document = helpers.get_db_config()
    except Exception as e:
        return render_template('error.html', error="Customer configuration document not found, please contact your administrator"), 500
    if 'scm_type' in config_document:
        scm_type = config_document['scm_type']
    else:
        scm_type = 'NA'

    return render_template('pipeline.html', scm_type=scm_type)


@frontend_blueprint.route('/frontend/workspace/git-projects', methods=['GET'])
def get_projects():
    try:
        projects = helpers.get_git_projects()
    except Exception as e:
        logging.warning(
            "Unable to retrieve list of projects from scm: %s" % traceback.format_exc())
        projects = {}
    return jsonify({'projects': projects}), 200


@frontend_blueprint.route('/frontend/workspace/git-repositories/<project_key>', methods=['GET'])
def get_repos(project_key):
    try:
        repos = helpers.get_git_repos(project_key)
    except Exception as e:
        logging.warning(
            "Unable to retrieve list of repos from scm: %s" % traceback.format_exc())
        repos = {}
    return jsonify({'repos': repos}), 200


@frontend_blueprint.route('/frontend/workspace/git-branches/<project_key>/<repo_name>', methods=['GET'])
def get_branches(project_key, repo_name):
    try:
        branches = helpers.get_git_branches(project_key, repo_name)
    except Exception as e:
        logging.warning(
            "Unable to retrieve list of branches from scm: %s" % traceback.format_exc())
        branches = {}
    return jsonify({'branches': branches}), 200


@frontend_blueprint.route('/frontend/workspace/create', methods=['GET'])
def create_workspace():
    return render_template('workspace.html')


@frontend_blueprint.route('/frontend/workspace/merge', methods=['GET'])
def create_merge_workspace():
    return render_template('workspace_merge.html')


@frontend_blueprint.route('/frontend/workspace/pipelines', methods=['GET'])
def pipelines():
    try:
        pipelines = helpers.get_pipelines()
    except Exception as e:
        logging.warning(
            "Unable to retrieve list of pipelines from database: %s" % traceback.format_exc())
        pipelines = {}
    return jsonify({'pipelines': pipelines}), 200
