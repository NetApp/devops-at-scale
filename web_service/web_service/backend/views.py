''' Web service API endpoints logic '''
import logging
from flask import Blueprint, jsonify, request, render_template
from flask import current_app as app
from web_service.helpers import helpers
from web_service.helpers.errors import GenericException
from web_service.kub.KubernetesAPI import KubernetesAPI
from web_service.jenkins.jenkins_api_secure import JenkinsAPI
from web_service.database.pipeline import Pipeline
from web_service.database.snapshot import Snapshot
from web_service.database.workspace import Workspace
import web_service.database.database as Database
from web_service.database.user import User
import web_service.database.workspace as workspace_obj
import time
from couchdb import http
import traceback

# TODO: Make exceptions specific
#   Should all exceptions be rendered to views.py?

backend_blueprint = Blueprint(
    'backend',
    __name__,
    template_folder='../templates')

'''
    API Error codes:
    # HTTP 4xx -- client-side error
    # HTTP 5xx -- server-side error
'''


# @backend_blueprint.before_app_first_request
# def setup():
#     helpers.onetime_setup_required()
#     response_object = {
#         'status': 'success',
#         'message': 'One time setup for Devops@Scale has been completed!'
#
#     }
#     return jsonify(response_object), 200


@backend_blueprint.route('/backend/', methods=['GET'])
def index():
    """
    Default index page for the backend API
    ---
    tags:
      - default
    responses:
      200:
        description: a welcome message should be returned

    """
    response_object = {
        'status': 'success',
        'message': 'Welcome to the DevOps@Scale backend!'

    }
    # TODO: Show dashboard by default
    return jsonify(response_object), 200


@backend_blueprint.route('/backend/version', methods=['GET'])
def version():
    """
    Display version information about the application
    ---
    tags:
      - default
    responses:
      200:
        description: return version information for this application

    """
    current_version = app.config['BUILD_AT_SCALE_VERSION']
    response_object = {
        'status': 'success',
        'message': "Build@Scale version: %s" % current_version

    }
    return jsonify(response_object), 200


def _get_config_from_db():
    # TODO: Should this method belong to database.py? Iff Exceptions can be redirected to web server
    """
    Helper method to establish a DB connection and fetch the configuration document
    Throws an exception if connection fails

    :raises GenericException 500 if DB connection fails
    :raises GenericException 500 if config document not found
    :return: DB Connection handler and Config document from the DB
    """
    # Retrieve customer configuration document from database
    try:
        connector = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as exc:
        raise GenericException(500,
                               GenericException.DB_CONNECTION_ERROR,
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")
    return connector, config_document


def _validate_input_form_params(form, required):
    """
    Validate if all required params are input in the web form
    :raises GenericException if one or more keys are missing
    :param form: input params from the web form
    :param required: required params for the API call
    :return: None
    """
    missing_params = helpers.check_for_missing_params(form, required)
    if len(missing_params) > 0:
        raise GenericException(400, "The following parameters " + str(missing_params) + " are required")


def _populate_workspace_details(workspace, input_form, config, merge):

    # Retrieve user document from db
    try:
        user_doc = helpers.get_db_user_document(request.form['username'])
    except:
        raise GenericException(500, "Error retrieving user information from database", "Database Exception")

    workspace['name'] = '-'.join([input_form['workspace-name'],
                                  request.form['username'],
                                  '-'.join(workspace['pipeline'].split('-')[1:]),  # extract project name from pipeline
                                  helpers.return_random_string(4)])
    # User details
    workspace['uid'] = user_doc['uid']
    workspace['gid'] = user_doc['gid']
    workspace['user_email'] = user_doc['email']
    workspace['username'] = input_form['username']
    # IDE deployment details
    workspace['pod_image'] = config['workspace_pod_image']
    workspace['build_cmd'] = "No build commands have been specified for this project"
    workspace['service_type'] = config['service_type']


def _complete_kubernetes_setup_for_workspace(workspace, merge=False):
    try:
        kube = KubernetesAPI.get_instance()
        kube_pvc_pod_response = kube.create_pvc_clone_and_pod(workspace, merge)
    except Exception as exc:
        logging.error("Unable to create Kubernetes Workspace PVC/Pod: %s" % traceback.format_exc())
        raise GenericException(500, "Unable to create Kubernetes Workspace PVC/Pod")

    if not helpers.verify_successful_response(kube_pvc_pod_response):
        logging.error("Unable to create Kubernetes Workspace PVC/Pod: %s" % kube_pvc_pod_response)
        raise GenericException(500, "Unable to create Kubernetes Workspace PVC/Pod")

    # workspace['clone_name'] is populated from KubernetesAPI (retrieved from PV-PVC mapping)
    workspace['clone_mount'] = "/mnt/" + workspace['clone_name']

    # Wait for IDE to be ready before returning
    # TODO: Change this to wait and proceed only when service is in Ready state (geta an IP assigned)
    try:
        time.sleep(60)
        workspace['ide'] = kube.get_service_url(workspace['service'])
    except:
        workspace['ide'] = "NA"
        logging.warning("WARNING: Unable to retrieve workspace URL")

    # Wait for pod to be ready before executing any commands
    # TODO: Add logic to proceed only when pod status is 'Running'
    # Set git user.email and user.name , we don't care if the command fails
    git_user_cmd = 'git config --global user.name %s' % request.form['username']
    git_email_cmd = 'git config --global user.email %s' % workspace['user_email']
    try:
        kube.execute_command_in_pod(workspace['pod'], git_user_cmd)
        kube.execute_command_in_pod(workspace['pod'], git_email_cmd)
    except:
        logging.warning("WARNING: Unable to configure GIT Username/Email on behalf of user: %s" %
                        traceback.format_exc())


def _record_new_workspace(db, workspace, merge=False):
    try:
        new_ws_document = Workspace(name=workspace['name'],
                                    clone=workspace['clone_name'],
                                    mount=workspace['clone_mount'],
                                    pipeline=workspace['pipeline'],
                                    username=workspace['username'],
                                    uid=workspace['uid'],
                                    gid=workspace['gid'],
                                    source_pvc=workspace['source_pvc'],
                                    pipeline_pvc=workspace['pipeline_pvc'],
                                    build_name=workspace['build_name'],
                                    pod=workspace['pod'],
                                    pvc=workspace['pvc'],
                                    pv=workspace['pv_name'],
                                    service=workspace['service'],
                                    ide_url=workspace['ide'])
        if merge:
            new_ws_document.source_workspace_pvc = workspace['source_workspace_pvc']
        new_ws_document.store(db)
    except http.ResourceConflict as exc:
        # If DB operation fails, delete workspace PVC created from previous step
        KubernetesAPI.get_instance().delete_pvc(workspace['pvc'])
        raise GenericException(500,
                               "Error recording new workspace in the DB, please contact your administrator",
                               "Database Exception")


def _setup_workspace(input_form, merge=False):
    # Retrieve customer configuration document from database
    connect, config = _get_config_from_db()

    # Validate if user hasn't exceeded the workspace limit
    try:
        exceeded, workspaces = workspace_obj.exceeded_workspace_count_for_user(input_form['username'],
                                                                               config['user_workspace_limit'])
        logging.debug("Workspace limit details:: %s %s" % (exceeded, str(workspaces)))
    except Exception as exc:
        logging.warning("WARNING: Unable to check user workspace limit (%s)  " % traceback.format_exc())
    if exceeded is True:
        raise GenericException(401, "User workspace limit of %s exceeded. "
                                    "Please delete one or more workspace(s) from %s and re-try"
                               % (config['user_workspace_limit'], workspaces))

    # setup initial workspace params
    workspace = dict()
    if merge:
        # Retrieve project name from source_workspace document
        try:
            source_ws_document = Database.get_document_by_name(connect, request.form['source-workspace-name'])
        except:
            error_msg = "Error retrieving source workspace information from database"
            logging.error("%s: %s" % (error_msg, traceback.format_exc()))
            raise GenericException(500, error_msg, "Database Exception")
        # populate the workspace details
        workspace['source_workspace_name'] = input_form['source-workspace-name']
        workspace['pipeline'] = source_ws_document['pipeline']
        workspace['build_name'] = request.form['build-name']
    else:
        workspace['pipeline'] = request.form['pipeline-name']
        # strip build_status and retain only the build_name
        workspace['build_name'] = request.form['build-name-with-status'].rsplit('_', 1)[0]

    _populate_workspace_details(workspace, input_form, config, merge)

    # Create Kube PVC, Pod, Service, and execute commands in Pod to complete workspace setup
    _complete_kubernetes_setup_for_workspace(workspace, merge)

    # Record new workspace document in DB
    _record_new_workspace(db=connect, workspace=workspace, merge=merge)

    return workspace


@backend_blueprint.route('/backend/workspace/create', methods=['POST'])
def workspace_create():
    """
    create developer workspace pod
    ---
    tags:
      - workspace
    parameters:
      - in: path
        name: workspace-name
        required: true
        description: Name of the workspace being created
        type: string
      - in: path
        name: build-name-with-status
        required: true
        description: build name (e.g. snapshot) from which clone should be created
        type: string
      - in: path
        name: username
        required: false
        description: username
        type: string
      - in: path
        name: pipeline-name
        required: true
        description: pipeline name of the SCM project
        type: string
    responses:
      200:
        description: workspace created successfully

    """
    # Validate input form parameters
    _validate_input_form_params(request.form, ['workspace-name', 'build-name-with-status', 'username', 'pipeline-name'])

    workspace = _setup_workspace(request.form)

    logging.debug("Workspace details:: %s" % str(workspace))
    return render_template('workspace_details.html', message="Workspace created successfully",
                           ontap_data_ip=app.config['ONTAP_DATA_IP'],
                           ontap_volume_name=workspace['clone_name'], workspace_ide=workspace['ide']), 200


@backend_blueprint.route('/backend/workspace/merge', methods=['POST'])
def workspace_merge():
    """
    Merge developer workspace pod
    ---
    tags:
      - workspace
    parameters:
      - in: path
        name: workspace-name
        required: true
        description: Name of the new merge workspace being created
        type: string
      - in: path
        name: build-name
        required: true
        description: Build name (e.g. snapshot) from which clone should be created
        type: string
      - in: path
        name: username
        required: true
        description: Username
        type: string
      - in: path
        name: source-workspace-name
        required: true
        description: Source workspace
        type: integer
    responses:
      200:
        description: merge workspace created successfully

    """
    # Validate input web form parameters from the application
    _validate_input_form_params(request.form, ['workspace-name', 'build-name', 'username', 'source-workspace-name'])

    workspace = _setup_workspace(request.form, merge=True)

    # Run the merge commands in the new workspace. source ws will be mounted at /source_workspace/git
    # Destination ws will be mounted at /workspace/git
    merge_cmd = '/usr/local/bin/build_at_scale_merge.sh /source_workspace/git /workspace/git'
    try:
        response = KubernetesAPI.get_instance().execute_command_in_pod(workspace['pod'], merge_cmd)
    except:
        logging.error("Unable to successfully complete git merge !" % traceback.format_exc())
        raise GenericException(500, "Unable to successfully complete merge!. Please contact your administrator")

    if response == "0":
        message = "Merge workspace created successfully!"
        logging.info("Response from workspace POD:: %s" % response)
    elif response == "1":
        message = "Merge workspace created successfully but merge conflicts were found. " \
                  "Please check the workspace for conflicts which need to be resolved"
        logging.warning("Response from workspace POD:: %s" % response)
    else:
        # If pod operations fail, delete the workspace PVC and the DB document created from previous steps
        KubernetesAPI.get_instance().delete_pvc(workspace['pvc'])
        db = helpers.connect_db()
        db.delete(workspace['name'])
        logging.error("Response from workspace POD:: %s" % response)
        raise GenericException(500, "Unable to successfully create a merged workspace! , please contact your administrator")

    return render_template('workspace_details.html', message=message,
                           ontap_volume_name=workspace['clone_name'], workspace_ide=workspace['ide']), 200


@backend_blueprint.route('/backend/workspace/delete', methods=['POST'])
def workspace_delete():
    """
    Delete developer workspace PVC, PV, Clone, Kube service and Kube pod
    ---
    tags:
      - workspace
    parameters:
      - in: path
        name: workspace-name
        required: true
        description: Name of the workspace to be deleted
        type: string

    responses:
      200:
        description:  workspace deleted successfully

    """
    #####
    # 1. Validate input form parameters
    # 2. Delete workspace PVC (Trident deletes associated PV and ONTAP clone)
    # 3. Delete workspace DB document
    #####
    # Validate input form parameters
    _validate_input_form_params(request.form, ['workspace-name'])

    try:
        helpers.delete_workspace(request.form['workspace-name'])
    except Exception as exc:
        logging.error("Unable to create Kubernetes Workspace PV/PVC/Pod: %s" % traceback.format_exc())
        raise GenericException(500, "Unable to delete workspace %s" % request.form['workspace-name'])
    response_object = {
        'status': 'success',
        'message': "Successfully deleted workspace: %s" % request.form['workspace-name']
    }
    return jsonify(response_object), 200


@backend_blueprint.route('/backend/workspace/purge', methods=['POST'])
def workspace_purge():
    """
    Purge workspaces older than workspace_purge_limit days
    The workspace limit is setup in the project's initial configuration
    ---
    tags:
      - workspace
    responses:
      200:
        description: workspaces have been purged successfully

    """
    count, purged_workspaces = workspace_obj.purge_old_workspaces()
    print("Got count and purged_workspaces", str(count))
    response = {'code': 200,
                'resource': 'purge',
                'customer_instance': app.config['DATABASE_NAME'],
                'message': "Purged %s workspaces" % count,
                'purged_workspaces': purged_workspaces,
                'status': 'COMPLETED'}
    return jsonify(response)


@backend_blueprint.route('/backend/pipeline/create', methods=['POST'])
def pipeline_create():
    """
    Setup a pipeline for an SCM project with a specific branch
    This endpoint is used by the DevOps admin
    At the end of successful execution, a Jenkins pipeline for the SCM project is created with required build parameters
    ---
    tags:
      - pipeline
    parameters:
      - in: path
        name: scm-url
        required: true
        description: SCM url for this project
        type: string
      - in: path
        name: scm-branch
        required: true
        description: SCM branch for this project
        type: string
      - in: path
        name: export-policy
        required: false
        description: export-policy for this project
        type: string
    responses:
      200:
        description: Pipeline has been created successfully

    """
    #####
    # 1. Validate input form parameters
    # 2. Get config document for setting up the pipeline details
    # 3. Gather storage details for creating PVC for this pipeline
    # 4. Create a Kube PVC (Trident creates a PV and an ONTAP volume, maps it to this PVC. We manage only the PVCs)
    # 5. Create Jenkins job
    # 6. Setup Jenkins purge job for this pipeline
    # 7. Record all pipeline details in database
    #####
    # Validate input web form parameters from the application
    _validate_input_form_params(request.form, ['scm-branch', 'scm-url'])

    connect, config = _get_config_from_db()

    # Gather storage details for creating PVC
    scm_project_url = helpers.sanitize_scm_url(request.form['scm-url'])
    if scm_project_url is None:
        raise GenericException(406, "Invalid SCM URL provided")
    pipeline = {
        'name': '-'.join(['pipeline',
                         helpers.extract_name_from_git_url(request.form['scm-url']),
                         request.form['scm-branch']]),
        'export_policy': request.form.get('export-policy', 'default'),  # set default export policy if not specified
        'scm_url': scm_project_url
    }

    # Create PVC. Once we create a Kube PVC, Trident creates an ONTAP volume and a PV for this PVC
    kube = KubernetesAPI.get_instance()
    vol_size = "10000"  # set default vol size to 10Gig, 10000 in MB
    # TODO: Change this to default SC from Kube -- list_all_storage_classes and read annotations to find default
    storage_class = config.get('storage_class')
    if storage_class == '':
        storage_class = None  # Don't set SC if SC is not passed in Helm, so that Kube can use the default storage class
    pvc_response = kube.create_pvc_resource(vol_name=pipeline['name'],
                                            vol_size=vol_size,
                                            storage_class=storage_class)
    if not helpers.verify_successful_response(pvc_response):
        raise GenericException(500, "Kubernetes PVC creation error")

    # setup params for Jenkins pipeline job
    pipeline_job = helpers.set_jenkins_job_params('ci-pipeline')
    pipeline_job['volume_claim_name'] = pvc_response['name']
    pipeline_job['scm_url'] = request.form['scm-url']
    pipeline_job['scm_branch'] = request.form['scm-branch']
    pipeline_job['kube_namespace'] = config['kube_namespace']

    # TODO: should this volume_name be populated as part of pvc_response? -
    #  but might want to handle if PVC creation has failed in KubernetesAPI.py
    pipeline_job['volume_name'] = kube.get_volume_name_from_pvc(pvc_response['name'])  # Get associated volume with PVC
    # TODO: This cannot be None.
    #  Validate after bootstrapping, PVCs for all services to be part of the config document.
    #  Remove this after including validation
    if config.get('scm_pvc_name') is None:
        pipeline_job['scm_volume_claim'] = kube.get_kube_resource_name(config['scm_volume'], 'pvc')

    purge_job = helpers.set_jenkins_job_params('trigger-purge')  # setup params for Jenkins purge job
    purge_job['kube_namespace'] = config['kube_namespace']

    # Create Jenkins CI and purge jobs for this pipeline
    # If Jenkins connection fails, delete the Kube PVC created from previous step
    try:
        jenkins = JenkinsAPI(config['jenkins_url'], config['jenkins_user'], config['jenkins_pass'])
    except Exception as exc:
        KubernetesAPI.get_instance().delete_pvc(pvc_response['name'])
        raise GenericException(500, "Jenkins connection error: %s" % str(exc))
    # If job creation fails, delete the Kube PVC created from previous step
    try:
        jenkins_job_url = jenkins.create_job(job_name=pipeline['name'], params=pipeline_job, form_fields=request.form)
        jenkins.create_job(job_name='purge_policy_enforcer', params=purge_job, form_fields=None)
    except Exception as exc:
        KubernetesAPI.get_instance().delete_pvc(pvc_response['name'])
        traceback.print_exc()
        raise GenericException(500, "Jenkins Job Creation Error: %s" % str(exc))

    # Complete gathering pipeline details
    pipeline['pvc'] = pvc_response['name']
    pipeline['volume'] = pipeline_job['volume_name']
    pipeline['jenkins_url'] = jenkins_job_url

    # Record new pipeline in database
    # TODO: type=pipeline document
    try:
        new_pipeline_document = Pipeline(**pipeline)
        new_pipeline_document.store(connect)
    except Exception as exc:
        # If DB operation fails, delete the Jenkins pipeline job, purge job and Kube PVC created from previous step
        jenkins.delete_job(pipeline['name'])
        KubernetesAPI.get_instance().delete_pvc(pvc_response['name'])
        raise GenericException(500, "Error recording new project in the DB, please contact your administrator",
                               "Database Exception" + str(exc))

    # TODO: Can we do a better in-page rendering instead of navigating to a raw JSON msg?
    return jsonify({'project_name': pipeline['name']}), 200


@backend_blueprint.route('/backend/pipeline/delete', methods=['POST'])
def pipeline_delete():
    """
    Delete a pipeline.
    This endpoint is used by the DevOps admin
    At the end of successful execution, Kube PVC, PV, ONTAP volume associated with the PVC, and
    Jenkins CI job associated with the pipeline are deleted.
    ---
    tags:
      - pipeline
    parameters:
      - in: path
        name: pipeline-name
        required: true
        description: Name of the pipeline to be deleted
        type: string
    responses:
      200:
        description:  Pipeline has been deleted successfully

    """
    #####
    # 1. Validate input form parameters
    # 2. Delete Kube PVC (Trident deletes the PV and ONTAP volume associated with the PVC)
    # 3. Delete DB pipeline document and Jenkins CI job
    #####
    # 1. Validate input form parameters
    _validate_input_form_params(request.form, ['pipeline-name'])

    # Don't delete pipeline if there are one or more workspaces associated with it
    ws_exists, workspaces = helpers.check_if_workspaces_exist_for_pipeline(request.form['pipeline-name'])
    if ws_exists:
        raise GenericException(500, "One or more workspaces for this pipeline %s exist."
                                    "Please re-try after deleting the following workspaces %s."
                                    % (request.form['pipeline-name'], workspaces))

    try:
        helpers.delete_pipeline(request.form['pipeline-name'])
    except Exception as exc:
        logging.error("Unable to delete pipeline: %s" % traceback.format_exc())
        raise GenericException(500, "Unable to delete pipeline %s :: %s" % (request.form['pipeline-name'], str(exc)))

    response_object = {
        'status': 'success',
        'message': "Successfully deleted workspace: %s" % request.form['pipeline-name']
    }
    return jsonify(response_object), 200


@backend_blueprint.route('/backend/volumeclaim/clone', endpoint='pvc_clone_create', methods=['POST'])
def volume_claim_clone():
    """
    Create Kube PVC clone
    This method is in place of snapshotting a source volume.
    Volume clones will be used instead of snapshots until Trident supports snapshot creation
    ---
    tags:
      - volumeclaim
    parameters:
      - in: body
        name: pvc_clone_name
        required: true
        description: name of the Kube PVC being created (cloned)
        type: string
      - in: body
        name: pvc_source_name
        required: true
        description: name of the Kube PVC that is being cloned from
        type: string
      - in: body
        name: build_status
        required: false
        description: specifies whether this clone is of a successful or failed build
        type: string
    responses:
      200:
        description: PVC Clone was created successfully

    """
    # TODO: document jenkins_build in docstring
    # TODO: do we need volume name?
    _validate_input_form_params(request.form, ['pvc_clone_name', 'pvc_source_name', 'build_status',
                                               'jenkins_build', 'volume_name'])
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")
    build_status = request.form['build_status'] or 'N/A'
    if build_status not in ["passed", "failed", "N/A"]:
        raise GenericException(406,
                               "Invalid build_status type parameter: accepted values - 'passed', 'failed', 'N/A'")

    # TODO: this name should be created in KubernetesAPI, but currently will impact create_pvc_and_pod()
    kube = KubernetesAPI.get_instance()

    pvc_clone_name = kube.get_kube_resource_name(request.form['pvc_clone_name'], 'pvc')
    status = kube.create_pvc_clone_resource(
        clone=pvc_clone_name, source=request.form['pvc_source_name'])
    # record snapshot in db
    db_connect = helpers.connect_db()
    if not db_connect:
        raise GenericException(500,
                               GenericException.DB_CONNECTION_ERROR,
                               "Database Exception")
    # TODO: Replace Snapshot doc with Clone document
    # TODO: Do we need volume or pvc_source_name?
    snapshot_doc = Snapshot(name=request.form['pvc_clone_name'],
                            pvc_name=pvc_clone_name,
                            # TODO: Why do we need volume? Also, this is not the clone volume name,
                            #  but the parent pipeline volume name which we use later for only querying.
                            #  Reflect key-name appropriately
                            parent_pipeline_pvc=request.form['pvc_source_name'],
                            volume=request.form['volume_name'],
                            pvc=pvc_clone_name,
                            jenkins_build=request.form['jenkins_build'],
                            build_status=build_status)
    snapshot_doc.store(db_connect)
    return jsonify(status)


@backend_blueprint.route('/backend/<pipeline_name>/buildclones',
                         endpoint='build_clones_list', methods=['GET'])
def build_clones_list(pipeline_name):
    """
    List all 'build' clones belonging to a pipeline
    ---
    tags:
      - clone
    parameters:
      - in: path
        name: pipeline_name
        required: true
        description: pipeline name to list clones from
        type: string
    responses:
      200:
        description: clones listed successfully

    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")
    # volume_name = helpers.get_volume_name_for_pipeline(pipeline_name)
    build_clones = helpers.get_all_builds_with_status_for_pipeline(pipeline_name)
    return jsonify(build_clones)


@backend_blueprint.errorhandler(GenericException)
def generic_error_handle(error):
    '''Handle GenericException'''
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@backend_blueprint.route('/backend/user/create', methods=['POST'])
def user_create():
    """
    create user
    ---
    tags:
      - user
    parameters:
      - in: path
        name: username
        required: true
        description: username
        type: string
      - in: path
        name: uid
        required: true
        description: User id
        type: integer
      - in: path
        name: gid
        required: true
        description: Group id
        type: integer
      - in: path
        name: email
        required: true
        description: email
        type: string
    responses:
      200:
        description: user was created successfully

    """
    # Retrieve customer configuration document from database
    try:
        database = helpers.connect_db()
    except Exception as e:
        raise GenericException(
            500, "Unable to connect to couchdb backend database, please contact your administrator")
    try:
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               GenericException.DB_CONNECTION_ERROR,
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")

    _validate_input_form_params(request.form, ['username', 'uid', 'gid', 'email'])

    # Check if user already exists
    current_user = helpers.get_db_user_document(request.form['username'])
    if current_user:
        raise GenericException(500,
                               "Error recording new user in the DB: username already exists",
                               "Database Exception")
    # Record new user in database
    try:
        new_user_document = User(name=request.form['username'],
                                 uid=request.form['uid'],
                                 gid=request.form['gid'],
                                 email=request.form['email'])
        new_user_document.store(database)
    except Exception as exc:
        raise GenericException(500,
                               "Error recording new user in the DB, \
                               please contact your administrator",
                               "Database Exception")
    return jsonify({'username': request.form['username']}), 200


@backend_blueprint.route('/backend/user/delete', methods=['POST'])
def user_delete():
    """
    delete user
    ---
    tags:
      - user
    parameters:
      - in: path
        name: username
        required: true
        description: username
        type: string
    responses:
      200:
        description: user was deleted successfully

    """
    # Retrieve customer configuration document from database
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")

    _validate_input_form_params(request.form, ['username'])

    # Check if user exists
    current_user = helpers.get_db_user_document(request.form['username'])
    if not current_user:
        raise GenericException(500,
                               "Error deleting user from the DB: user does not exist",
                               "Database Exception")
    # Delete user from database
    try:
        database.delete(current_user)
    except Exception as exc:
        raise GenericException(500,
                               "Error deleting user from the DB, \
                               please contact your administrator",
                               "Database Exception")
    return jsonify({'message': "user %s deleted successfully " % request.form['username']}), 200


@backend_blueprint.route(
    '/backend/admin/ssl/modify', methods=['POST'])
def storage_service_level_modify():
    """
    Modify Storage service level of the ONTAP volume
    ---
    tags:
      - admin
    parameters:
      - in: body
        name: project_name
        required: true
        description: Name of the project to modify ssl
        type: string
      - in: body
        name: ssl_name
        required: true
        description: Name of the ssl to be applied [performance, extreme, value]
        type: string
    responses:
      200:
        description: Storage service level of volume has been modified successfully

    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               GenericException.DB_CONFIG_DOC_NOT_FOUND,
                               "Database Exception")

    _validate_input_form_params(request.form, ['project_name', 'ssl_name'])

    volume_name = helpers.replace_ontap_invalid_char(
        request.form['project_name'])
    helpers.modify_ssl_for_volume(volume_name, request.form['ssl_name'])
    return jsonify({'message': "Storage service level has been modified to %s for project %s successfully " % (request.form['ssl_name'], volume_name)}), 200
