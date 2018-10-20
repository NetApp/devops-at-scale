''' Web service API endpoints logic '''
import logging
from flask import Blueprint, jsonify, request, render_template
from flask import current_app as app
from web_service.ontap.ontap_service import OntapService
from web_service.helpers import helpers
from web_service.helpers.errors import GenericException
from web_service.kub.KubernetesAPI import KubernetesAPI
from web_service.jenkins.jenkins_api_secure import JenkinsAPI
from web_service.database.project import Project
from web_service.database.snapshot import Snapshot
from web_service.database.workspace import Workspace
import web_service.database.database as Database
from web_service.database.user import User
import web_service.database.workspace as workspace_obj
import web_service.database.snapshot as snapshot
import time
from pdb import set_trace as bp
import requests
import traceback

backend_blueprint = Blueprint(
    'backend',
    __name__,
    template_folder='../templates')

'''
    API Error codes:
    # HTTP 4xx -- client-side error
    # HTTP 5xx -- server-side error
'''


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
        'message': 'Welcome to the Build@Scale backend!'

    }
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
    version = app.config['BUILD_AT_SCALE_VERSION']
    response_object = {
        'status': 'success',
        'message': "Build@Scale version: %s" % version

    }
    return jsonify(response_object), 200


@backend_blueprint.route('/backend/workspace/create', methods=['POST'])
@helpers.setup_required
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
        name: build-name
        required: true
        description: build name (e.g. snapshot) from which clone should be created
        type: string
      - in: path
        name: username
        required: false
        description: username
        type: string
     - in: path
       name: project-name
       required: true
       description: the project/pipeline name
       type: string
    responses:
      200:
        description: workspace created successfully

    """
    # Retrieve customer configuration document from database
    try:
        database = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")

    expected_keys = ['workspace-name',
                     'build-name', 'username', 'project-name']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(
            400, "workspace-name, build-name, project-name and username are required")

    username = request.form['username']
    try:
        user_doc = helpers.get_db_user_document(username)
        uid = user_doc['uid']
        gid = user_doc['gid']
        email = user_doc['email']
    except:
        raise GenericException(
            500, "Error retrieving user information from database", "Database Exception")

    try:
        exceeded, workspaces = workspace_obj.exceeded_workspace_count_for_user(
            uid, config_document['user_workspace_limit'])
    except Exception as exc:
        logging.warning("WARNING: Unable to check user workspace limit (%s)  " %
                        traceback.format_exc())
    if exceeded is True:
        raise GenericException(
            401, "Please delete one or more workspace(s) from %s and re-try" % workspaces)
    # populate the workspace details
    namespace = 'default'
    workspace = dict()
    workspace['project'] = request.form['project-name']
    workspace['snapshot'] = request.form['build-name']
    volume_name = request.form['volume-name']
    workspace['clone'] = volume_name + \
        "_workspace" + helpers.return_random_string(4)
    workspace['kb_clone_name'] = helpers.replace_kube_invalid_characters(
        workspace['clone'])
    workspace['uid'] = uid
    workspace['gid'] = gid
    workspace['username'] = username
    workspace['clone_size_mb'] = "900"
    workspace['pod_image'] = config_document['workspace_pod_image']
    workspace['clone_mount'] = "/mnt/" + workspace['kb_clone_name']
    workspace['build_cmd'] = "No build commands have been specified for this project"
    workspace['service_type'] = config_document['service_type']

    try:
        ontap_instance = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                                      config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
        ontap_data_ip = ontap_instance.data_ip
        status, vol_size = ontap_instance.create_clone(volume_name,
                                                       workspace['uid'], workspace['gid'],
                                                       workspace['clone'], workspace['snapshot'])
    except Exception as exc:
        logging.error("Unable to create ontap workspace clone volume: %s" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to create ontap workspace clone volume")

    if not helpers.verify_successful_response(status):
        logging.error("ONTAP Clone Creation Error: %s", repr(status))
        return render_template('error.html', error="Workspace clone creation error"), 400
    try:
        kube = KubernetesAPI()
    except Exception as exc:
        logging.error("Unable to connect to Kubernetes: %s" %
                      traceback.format_exc())
        raise GenericException(500, "Unable to connect to Kubernetes")
    try:

        kube_pv_pvc_pod_response = kube.create_pv_and_pvc_and_pod(workspace, vol_size,
                                                                  'default', ontap_data_ip)
    except Exception as exc:
        logging.error("Unable to create Kubernetes Workspace PV/PVC/Pod: %s" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to create Kubernetes Workspace PV/PVC/Pod")

    for response in kube_pv_pvc_pod_response:
        status.append(response)

    if not helpers.verify_successful_response(status):
        logging.error(
            "Unable to create Kubernetes Workspace PV/PVC/Pod: %s" % response)
        raise GenericException(
            500, "Unable to create Kubernetes Workspace PV/PVC/Pod")

    workspace_pod = workspace['kb_clone_name'] + "-pod"


    # Record new workspace in database
    try:
        new_ws_document = Workspace(name=workspace['clone'],
                                    project=workspace['project'],
                                    username=workspace['username'],
                                    uid=workspace['uid'],
                                    gid=workspace['gid'],
                                    parent_snapshot=workspace['snapshot'],
                                    pod_name=workspace_pod)
        new_ws_document.store(database)
    except Exception:
        raise GenericException(500,
                               "Error recording new workspace in the DB, \
                               please contact your administrator",
                               "Database Exception")
    # Wait for pod to be ready before executing any commands
    time.sleep(15)
    # Set git user.email and user.name , we don't care if the command fails
    git_user_cmd = [
        'git',
        'config',
        '--global',
        'user.name',
        username
    ]
    git_email_cmd = [
        'git',
        'config',
        '--global',
        'user.email',
        email
    ]
    try:
        response = kube.execute_command_in_pod(
            workspace_pod, namespace, git_user_cmd)
        response = kube.execute_command_in_pod(
            workspace_pod, namespace, git_email_cmd)
    except:
        logging.warning("WARNING: Unable to configure GIT Username/Email on behalf of user: %s" %
                        traceback.format_exc())
    # Wait for IDE to be ready before returning
    try:
        time.sleep(60)
        workspace_ide = kube.get_service_url(workspace['kb_clone_name'] + "-service")
    except:
        workspace_ide = "NA"
        logging.warning("WARNING: Unable to retrieve workspace URL")
    message = "Workspace created successfully!"
    return render_template('workspace_details.html',message=message, ontap_data_ip=ontap_data_ip,ontap_volume_name=workspace['clone'],workspace_ide=workspace_ide), 200

@backend_blueprint.route('/backend/workspace/merge', methods=['POST'])
@helpers.setup_required
def workspace_merge():
    """
    merge developer workspace pod
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
    # Retrieve customer configuration document from database
    try:
        database = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    expected_keys = ['workspace-name', 'build-name',
                     'username', 'source-workspace-name']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(
            400, "workspace-name, build-name, username and source-workspace-name are required")

    username = request.form['username']
    try:
        user_doc = helpers.get_db_user_document(username)
        uid = user_doc['uid']
        gid = user_doc['gid']
        email = user_doc['email']
    except:
        raise GenericException(
            500, "Error retrieving user information from database", "Database Exception")

    try:
        exceeded, workspaces = workspace_obj.exceeded_workspace_count_for_user(
            uid, config_document['user_workspace_limit'])
    except Exception as exc:
        logging.warning("WARNING: Unable to check user workspace limit (%s)  " %
                        traceback.format_exc())
    if exceeded is True:
        raise GenericException(
            401, "User workspace limit exceeded , please delete one or more workspace(s) from %s and re-try" % workspaces)

    # retrieve project name from on source-workspace document
    try:
        source_ws_document = Database.get_document_by_name(
            database, request.form['source-workspace-name'])
        project = source_ws_document['project'].rstrip()
    except:
        error_msg = "Error retrieving source workspace information from database"
        logging.error("%s: %s" % (error_msg, traceback.format_exc()))
        raise GenericException(500, error_msg, "Database Exception")

    # populate the workspace details
    workspace = dict()
    workspace['source_workspace_name'] = helpers.replace_kube_invalid_characters(
        request.form['source-workspace-name'])
    namespace = 'default'
    workspace['project'] = project
    workspace['snapshot'] = request.form['build-name']
    volume_name = helpers.replace_ontap_invalid_char(workspace['project'])
    workspace['clone'] = volume_name + \
        "_workspace" + helpers.return_random_string(4)
    workspace['kb_clone_name'] = helpers.replace_kube_invalid_characters(
        workspace['clone'])
    workspace['uid'] = uid
    workspace['gid'] = gid
    workspace['username'] = username
    workspace['clone_size_mb'] = "900"
    workspace['pod_image'] = config_document['workspace_pod_image']
    workspace['clone_mount'] = "/mnt/" + workspace['kb_clone_name']
    workspace['build_cmd'] = "No build commands have been specified for this project"
    workspace['service_type'] = config_document['service_type']

    try:
        ontap_instance = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                                      config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
        ontap_data_ip = ontap_instance.data_ip

        status, vol_size = ontap_instance.create_clone(volume_name,
                                                       workspace['uid'], workspace['gid'],
                                                       workspace['clone'], workspace['snapshot'])
    except Exception as exc:
        logging.error("Unable to create ontap workspace clone volume: %s" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to create ontap workspace clone volume")

    if not helpers.verify_successful_response(status):
        logging.error("ONTAP Clone Creation Error: %s", repr(status))
        return render_template('error.html', error="Workspace clone creation error"), 400

    try:
        kube = KubernetesAPI()
    except Exception as exc:
        logging.error("Unable to connect to Kubernetes: %s" %
                      traceback.format_exc())
        raise GenericException(500, "Unable to connect to Kubernetes")
    try:
        kube_pv_pvc_pod_response = kube.create_pv_and_pvc_and_pod(workspace, vol_size,
                                                                  'default', ontap_data_ip)
    except Exception as exc:
        logging.error("Unable to create Kubernetes Workspace PV/PVC/Pod: %s" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to create Kubernetes Workspace PV/PVC/Pod")
    for response in kube_pv_pvc_pod_response:
        status.append(response)

    if not helpers.verify_successful_response(status):
        logging.error(
            "Unable to create Kubernetes Workspace PV/PVC/Pod: %s" % response)
        raise GenericException(
            500, "Unable to create Kubernetes Workspace PV/PVC/Pod")

    workspace_pod = workspace['kb_clone_name'] + "-pod"
    try:
        workspace_ide = kube.get_service_url(
            workspace['kb_clone_name'] + "-service")
    except Exception as exc:
        logging.error("Unable to determine workspace kubernetes service url: %s" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to determine workspace kubernetes service url, please contact your administrator")

    # Record new workspace in database
    try:
        new_ws_document = Workspace(name=workspace['clone'],
                                    project=workspace['project'],
                                    username=workspace['username'],
                                    uid=workspace['uid'],
                                    gid=workspace['gid'],
                                    parent_snapshot=workspace['snapshot'],
                                    pod_name=workspace_pod)
        new_ws_document.store(database)
    except Exception:
        raise GenericException(500,
                               "Error recording new workspace in the DB, please contact your administrator",
                               "Database Exception")

    # Wait for pod to be ready before executing any commands
    time.sleep(180)
    # Set git user.email and user.name , we don't care if the command fails
    git_user_cmd = [
        'git',
        'config',
        '--global',
        'user.name',
        username
    ]
    git_email_cmd = [
        'git',
        'config',
        '--global',
        'user.email',
        email
    ]
    try:
        response = kube.execute_command_in_pod(
            workspace_pod, namespace, git_user_cmd)
        response = kube.execute_command_in_pod(
            workspace_pod, namespace, git_email_cmd)
    except:
        logging.warning("WARNING: Unable to configure GIT Username/Email on behalf of user: %s" %
                        traceback.format_exc())

    # run the merge commands in the new workspace
    # source ws will be mounted at /source_workspace/git
    # destination ws will be mounted at /workspace/git
    merge_cmd = [
        '/usr/local/bin/build_at_scale_merge.sh',
        '/source_workspace/git',
        '/workspace/git']
    try:
        response = kube.execute_command_in_pod(
            workspace_pod, namespace, merge_cmd)
    except:
        logging.error("Unable to successfully complete git merge !" %
                      traceback.format_exc())
        raise GenericException(
            500, "Unable to successfully complete merge ! , please contact your administrator")

    if response == "0":
        message = "Merge workspace created successfully!"
    elif response == "1":
        message = "Merge workspace created successfully but merge conflicts were found. Please check the workspace for conflicts which need to be resolved"
    else:
        raise GenericException(
            500, "Unable to successfully complete merge ! , please contact your administrator")
    # Wait for IDE to be ready before returning
    time.sleep(5)
    return render_template('workspace_details.html',message=message, ontap_data_ip=ontap_data_ip,ontap_volume_name=workspace['clone'],workspace_ide=workspace_ide), 200

@backend_blueprint.route('/backend/workspace/delete', methods=['POST'])
@helpers.setup_required
def workspace_delete():
    """
    delete developer workspace pod
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
    # Retrieve customer configuration document from database
    try:
        database = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    expected_keys = ['workspace-name']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(
            400, "workspace-name is required")
    try:
        helpers.delete_workspace(request.form['workspace-name'])
    except Exception as exc:
        logging.error("Unable to create Kubernetes Workspace PV/PVC/Pod: %s" %
                      traceback.format_exc())
        raise GenericException(500, "Unable to delete workspace %s" % request.form['workspace-name'])
    response_object = {
        'status': 'success',
        'message': "Successfully deleted workspace: %s" % request.form['workspace-name']
    }
    return jsonify(response_object), 200



@backend_blueprint.route(
    '/backend/workspace/purge', methods=['POST'])
def workspace_purge():
    """
    purge workspaces greater than workspace_purge_limit set in project config
    ---
    tags:
      - workspace
    parameters:

    responses:
      200:
        description: workspace was modified successfully

    """
    count, purged_workspaces = workspace_obj.purge_old_workspaces()
    response = {'code': 200,
                'resource': 'purge',
                'customer_instance': app.config['DATABASE_NAME'],
                'message': "Purged %s workspaces" % count,
                'purged_workspaces': purged_workspaces,
                'status': 'COMPLETED'}
    return jsonify(response)


@backend_blueprint.route('/backend/project/create', methods=['POST'])
@helpers.setup_required
def project_create():
    """
    create project
    ---
    tags:
      - project
    parameters:
      - in: path
        name: scm-url
        required: true
        description: git url for this project
        type: string
      - in: path
        name: scm-branch
        required: true
        description: git branch for this project
        type: string
      - in: path
        name: export-policy
        required: false
        description: export-policy for this project
        type: string
    responses:
      200:
        description: project was created successfully

    """
    # Retrieve customer configuration document from database

    try:
        database = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    expected_keys = ['scm-branch', 'scm-url']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(400, "SCM URL and SCM Branch are required")

    scm_project_url = helpers.sanitize_scm_url(request.form['scm-url'])

    if scm_project_url is None:
        raise GenericException(406, "Invalid SCM URL provided")

    project_name = helpers.extract_name_from_git_url(request.form['scm-url'])
    project_name += "-" + request.form['scm-branch']
    # Kubernetes does not like _
    project_name = helpers.replace_kube_invalid_characters(project_name)
    # ONTAP does not like -
    project_name_no_dashes = helpers.replace_ontap_invalid_char(project_name)

    ontap_instance = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                                  config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
    ontap_data_ip = ontap_instance.data_ip
    vol_uid = "0"
    vol_gid = "0"
    vol_size = "10000"
    if 'export_policy' in request.form:
        vol_export_policy = request.form['export-policy']
    else:
        vol_export_policy = 'default'
    try:
        status, vol_size = ontap_instance.create_volume(project_name_no_dashes,
                                                        vol_size, vol_uid, vol_gid, vol_export_policy)
    except Exception as e:
        error_message = "Unable to create backing ontap volume for pipeline"
        logging.error("Unable to create backing ontap volume for pipeline:\n %s" %
                      traceback.format_exc())
        raise GenericException(500, error_message)

    if not helpers.verify_successful_response(status):
        error_message = "Unable to create backing ontap volume for pipeline: "
        try:
            error = status[0]['error_message'].split('(', 1)[0]
        except KeyError:
            error = ''
        error_message = error_message + error
        raise GenericException(500, error_message)

     # if volume creation successful, autosupport log
     # display a warning if this step fails , we don't want to exit out
    try:
        pass
        # helpers.autosupport(project_name_no_dashes, vol_size)
    except Exception as e:
        logging.warning(
            "WARNING: Unable to generate autosupport log (%s)  " % str(e))

    kube_namespace = 'default'
    pv_and_pvc_responses = KubernetesAPI().create_pv_and_pvc(
        project_name, vol_size,
        kube_namespace,
        ontap_data_ip)

    for response in pv_and_pvc_responses:
        status.append(response)

    if not helpers.verify_successful_response(status):
        raise GenericException(500, "Kubernetes PV/PVC Error")

    try:
        jenkins = JenkinsAPI(config_document['jenkins_url'],
                             config_document['jenkins_user'],
                             config_document['jenkins_pass'])
    except Exception as exc:
        raise GenericException(500, "Jenkins connection error: %s" % str(exc))
    params = dict()
    params['type'] = 'ci-pipeline'
    params['volume_name'] = project_name_no_dashes
    params['git_volume'] = config_document['git_volume']
    params['service_username'] = config_document['service_username']
    params['service_password'] = config_document['service_password']
    params['broker_url'] = config_document['web_service_url']
    params['container_registry'] = config_document['container_registry']

    try:
        jenkins.create_job(project_name, params, request.form)
    except Exception as exc:
        raise GenericException(
            500, "Jenkins Job Creation Error: %s" % str(exc))

    jenkins_url = config_document['jenkins_url'] + "job/" + project_name
    # Record new project in database
    try:
        new_project_document = Project(name=project_name,
                                       volume=project_name_no_dashes,
                                       export_policy=vol_export_policy,
                                       scm_url=scm_project_url,
                                       jenkins_url=jenkins_url)
        new_project_document.store(database)
    except Exception as exc:
        raise GenericException(500,
                               "Error recording new project in the DB, \
                               please contact your administrator",
                               "Database Exception" + str(exc))
    # create trigger-purge jenkins job if not already done
    jenkins_account = dict()
    jenkins_account['url'] = config_document['jenkins_url']
    jenkins_account['username'] = config_document['jenkins_user']
    jenkins_account['password'] = config_document['jenkins_pass']

    try:
        helpers.create_purge_jenkins_job(
            job='purge_policy_enforcer', account=jenkins_account)
    except RuntimeError as exc:
        raise GenericException(
            500, "Jenkins Job Creation Error: 'purge_policy_enforcer' ")
    # need not return project_volume once we start storing volume info in DB
    return jsonify({'project_name': project_name,
                    'project_volume': project_name_no_dashes}), 200

@backend_blueprint.route('/backend/project/delete', methods=['POST'])
@helpers.setup_required
def project_delete():
    """
    delete project
    ---
    tags:
      - project
    parameters:
      - in: path
        name: project-name
        required: true
        description: Name of the project/pipeline to be deleted
        type: string

    responses:
      200:
        description:  project deleted successfully

    """
    # Retrieve customer configuration document from database
    try:
        database = helpers.connect_db()
        config_document = helpers.get_db_config()
    except Exception as e:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer configuration document not found, please contact your administrator",
                               "Database Exception")
    expected_keys = ['project-name']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(
            400, "project-name is required")
    try:
        helpers.delete_project(request.form['project-name'])
    except Exception as exc:
        logging.error("Unable to delete project: %s" %
                      traceback.format_exc())
        raise GenericException(500, "Unable to delete project %s" % request.form['project-name'])
    response_object = {
        'status': 'success',
        'message': "Successfully deleted workspace: %s" % request.form['project-name']
    }
    return jsonify(response_object), 200

@backend_blueprint.route('/backend/<volume_name>/snapshots',
                         endpoint='snapshot_list', methods=['GET'])
@helpers.setup_required
def snapshot_list(volume_name):
    """
    List all snapshots
    ---
    tags:
      - snapshot
    parameters:
      - in: path
        name: volume_name
        required: true
        description: parent volume name to list snapshots
        type: string
    responses:
      200:
        description: snapshot was created successfully

    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")
    ontap = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                         config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
    snapshots = ontap.get_snapshot_list(volume_name)
    return jsonify(snapshots)


@backend_blueprint.route('/backend/snapshot/create', endpoint='snapshot_create', methods=['POST'])
@helpers.setup_required
def snapshot_create():
    """
    Create snapshot from volume
    ---
    tags:
      - snapshot
    parameters:
      - in: body
        name: snapshot_name
        required: true
        description: name of the snapshot being created
        type: string
      - in: body
        name: volume_name
        required: true
        description: name of the volume that needs to be snapshot
        type: string
      - in: body
        name: build_status
        required: false
        description: specifies whether this snapshot is of a successful or failed build
        type: string
    responses:
      200:
        description: snapshot was created successfully

    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")
    ontap = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                         config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
    build_status = request.form['build_status'] or 'N/A'
    if build_status not in ["passed", "failed", "N/A"]:
        raise GenericException(406,
                               "Invalid build_status type parameter: accepted values - 'passed', 'failed', 'N/A'")
    status = ontap.create_snapshot(
        request.form['volume_name'], request.form['snapshot_name'])
    # record snapshot in db
    db_connect = helpers.connect_db()
    if not db_connect:
        raise GenericException(500,
                               "Database connection failure, please contact your administrator",
                               "Database Exception")
    snapshot_doc = Snapshot(name=request.form['snapshot_name'],
                            volume=request.form['volume_name'],
                            jenkins_build=request.form['jenkins_build'],
                            build_status=build_status
                            )
    snapshot_doc.store(db_connect)
    return jsonify(status)


@backend_blueprint.route('/backend/snapshot/delete', endpoint='snapshot_delete', methods=['DELETE'])
@helpers.setup_required
def snapshot_delete():
    """
    Delete snapshot
    ---
    tags:
      - snapshot
    parameters:
      - in: body
        name: snapshot_name
        required: true
        description: name of the snapshot being created
        type: string
      - in: body
        name: volume_name
        required: true
        description: name of the volume that needs to be snapshot
        type: string
    responses:
      200:
        description: snapshot was deleted successfully
    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")
    ontap = OntapService(config_document['ontap_api'], config_document['ontap_apiuser'], config_document['ontap_apipass'],
                         config_document['ontap_svm_name'], config_document['ontap_aggr_name'], config_document['ontap_data_ip'])
    status = ontap.delete_snapshot(
        request.form['volume_name'], request.form['snapshot_name'])
    return jsonify(status)

# @backend_blueprint.errorhandler(helpers.DatabaseException)
# @backend_blueprint.errorhandler(helpers.MissingParameter)


@backend_blueprint.errorhandler(GenericException)
def generic_error_handle(error):
    '''Handle GenericException'''
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@backend_blueprint.route('/backend/snapshot/purge', endpoint='snapshot_purge', methods=['POST'])
@helpers.setup_required
def snapshot_purge():
    """
    Purge snapshots
    ---
    tags:
      - snapshot
    parameters:
      - in: body
        name: snapshot_type
        required: false
        description: type of snapshots to be purged {"scm" or "ci"}
        type: string
    responses:
      200:
        description: "web_service app is tied to a singe customer instance.
        Calling this purge API will purge both SCM and CI snapshots from this customer instance"
    """
    db_connect = helpers.connect_db()
    customer_config = helpers.get_db_config()
    if not db_connect or not customer_config:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")

    if 'type' in request.form:
        snapshot_type = request.form['type']
        count = snapshot.purge(snapshot_type)
        if snapshot_type not in ["scm", "ci"]:  # invalid type
            raise GenericException(406,
                                   "Invalid snapshot type parameter: accepted values - 'scm', 'ci'")
        msg = "Purged %s %s snapshots" % (count, snapshot_type)
    else:
        count_scm = snapshot.purge("scm")
        count_ci = snapshot.purge("ci")
        msg = "Purged %s SCM and %s CI snapshots" % (count_scm, count_ci)

    response = {'code': 200,
                'resource': 'purge',
                'customer_instance': app.config['DATABASE_NAME'],
                'message': msg,
                'status': 'COMPLETED'}

    return jsonify(response)


@backend_blueprint.route('/backend/user/create', methods=['POST'])
@helpers.setup_required
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
        config_document = None
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")
    if not config_document:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")

    expected_keys = ['username', 'uid', 'gid', 'email']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(400, "username,uid,gid, and email are required")

    username = request.form['username']
    uid = request.form['uid']
    gid = request.form['gid']
    email = request.form['email']
    # Check if user already exists
    current_user = helpers.get_db_user_document(username)
    if current_user:
        raise GenericException(500,
                               "Error recording new user in the DB: username already exists",
                               "Database Exception")
    # Record new user in database
    try:
        new_user_document = User(name=username, uid=uid, gid=gid, email=email)
        new_user_document.store(database)
    except Exception as exc:
        raise GenericException(500,
                               "Error recording new user in the DB, \
                               please contact your administrator",
                               "Database Exception")
    return jsonify({'username': username}), 200


@backend_blueprint.route('/backend/user/delete', methods=['POST'])
@helpers.setup_required
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
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")

    expected_keys = ['username']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(400, "username is required")

    username = request.form['username']
    # Check if user exists
    current_user = helpers.get_db_user_document(username)
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
    return jsonify({'message': "user %s deleted successfully " % username}), 200


@backend_blueprint.route(
    '/backend/admin/ssl/modify', methods=['POST'])
@helpers.setup_required
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
        description: Name of the ssl to be applied: [performance, extreme, value]
        type: string
    responses:
      200:
        description: Storage service level of volume has been modified successfully

    """
    database = helpers.connect_db()
    config_document = helpers.get_db_config()
    if not config_document:
        raise GenericException(500,
                               "Customer config doc not found, please contact your administrator",
                               "Database Exception")

    expected_keys = ['project_name', 'ssl_name']
    if not helpers.request_validator(request.form, expected_keys):
        raise GenericException(400, "project_name and ssl_name are required")

    volume_name = helpers.replace_ontap_invalid_char(
        request.form['project_name'])
    helpers.modify_ssl_for_volume(volume_name, request.form['ssl_name'])
    return jsonify({'message': "Storage service level has been modified to %s for project %s successfully " % (request.form['ssl_name'], volume_name)}), 200
