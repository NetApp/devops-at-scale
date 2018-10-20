''' helper methods '''
import json
import logging
import os
import random
import re
import requests
import string
from flask import current_app as app
import web_service.database.database as Database
from web_service.ontap.ontap_service import OntapService
from web_service.jenkins.jenkins_api_secure import JenkinsAPI
from web_service.kub.KubernetesAPI import KubernetesAPI
from web_service.helpers.errors import GenericException
import sys
import inspect
import traceback
from functools import wraps
import netapp_lib.api.zapi
sys.path.insert(0, os.path.dirname(inspect.getfile(netapp_lib.api.zapi)))

HAS_NETAPP_LIB = False
try:
    from netapp_lib.api.zapi import zapi
    from netapp_lib.api.zapi import errors as zapi_errors
    HAS_NETAPP_LIB = True
except:
    HAS_NETAPP_LIB = False

ENCPASS='Build@Scale@99!'

def extract_name_from_git_url(url):
    '''Extract project name from SCM URL'''
    repo_name = os.path.basename(url)
    return re.match(r"^(.*?)(\.git)?$", repo_name).group(1)


def extract_url_from_git_ssh_url(url):
    '''Extract project name from SSH URL'''
    needle = r'git@(\S+):(.*)\.git'
    matched = re.match(needle, url)
    if matched:
        return "/".join(matched.group(1, 2))
    return None


def extract_url_from_git_http_url(url):
    '''Extract project URL name from SCM URL'''
    needle = r'(https?://)(\S+@)?(.*)\.git'
    matched = re.match(needle, url)
    if matched:
        return "".join(matched.group(1, 3))
    return None


def verify_successful_response(responses):
    '''Verify if response is success'''
    success = True
    for response in responses:
        if response['code'] > 399:
            success = False
    return success


def get_first_failure(responses):
    '''Find failed response from list of responses'''
    for response in responses:
        if response['code'] > 399:
            return response
    raise KeyError


def return_random_string(length):
    '''Returns random ascii string'''
    def rand_str_func(n): return ''.join(
        [random.choice(string.ascii_lowercase) for i in range(n)])
    rand_str = rand_str_func(length)
    return rand_str


def format_response(response_collection):
    '''Re-format responses to a dict'''
    return {
        "code": response_collection[0]['code'],
        "message": "%s created" % response_collection[0]['resource'],
        "status": response_collection[0]['status'],
        "payload": response_collection
    }


def sanitize_scm_url(url):
    '''Transform ssh url to http'''
    if url.startswith(("http://", "https://")):
        # we could strip the username@ and .git
        return extract_url_from_git_http_url(url)
    if url.startswith("git@"):
        # ssh format
        return extract_url_from_git_ssh_url(url)
    return None


def request_validator(request_form_object, keys):
    '''Check if all items in 'keys' are present in request-form'''
    for key in keys:
        try:
            if not request_form_object[key]:
                return False
        except KeyError:
            return False
    return True


def create_pvc_notification(customer_pvcs):
    ''' Creates flash message for updating jenkins url following pvc creation '''
    pvc_notification = "Have you created your Jenkins instance? \
                        Please run Helm commands noted in documentation.</br>GitLab PVCs: %s, %s, %s, %s</br>Jenkins PVC: %s" \
                        % (customer_pvcs['gitlab-data'], customer_pvcs['gitlab-etc'],
                           customer_pvcs['gitlab-postgresql'], customer_pvcs['gitlab-redis'],
                           customer_pvcs['jenkins'])
    return pvc_notification


def replace_ontap_invalid_char(text):
    '''
        Replace characters which are not supported by ontap with underscores
    '''
    return re.sub(r"[-|.]", r"_", text)


def replace_kube_invalid_characters(text):
    '''
        Replace characters which are not supported by kubernetes with dashes
    '''
    return re.sub(r"[_]", r"-", text)


def connect_db():
    '''Connect to database and retrieve config document'''
    try:
        database = Database.connect(app.config['DATABASE_URL'], app.config['DATABASE_USER'],
                                    app.config['DATABASE_PASSWORD'], app.config['DATABASE_NAME'])
    except Exception as e:
        print("Unable to connect to database: %s" % traceback.format_exc())
        raise e
    return database


def get_db_config():
    '''Connect to database and retrieve config document'''
    database = connect_db()
    try:
        config_document = Database.get_document_by_name(
            database, 'configuration')
    except Exception as e:
        print("Unable to retrieve configuration document from database: %s" %
              traceback.format_exc())
        raise e
    return config_document


def connect_jenkins(account=None):
    if account is None:
        config_document = get_db_config()
        account = dict()
        account['url'] = config_document['jenkins_url']
        account['username'] = config_document['jenkins_user']
        account['password'] = config_document['jenkins_pass']
    return JenkinsAPI(account['url'],
                      account['username'],
                      account['password'])


def get_db_user_document(username):
    '''Connect to database and retrieve user document'''
    database = connect_db()
    user_document = None
    users = Database.get_documents_by_type(database, 'user')
    for user in users:
        if user['name'] == username:
            user_document = user
    return user_document


def create_purge_jenkins_job(job, account):
    '''Creates a Jenkins job'''
    jenkins = connect_jenkins(account)
    config = get_db_config()
    job_details = dict()
    job_details['type'] = 'trigger-purge'
    job_details['web_service_url'] = config['web_service_url']
    job_details['web_service_username'] = config['service_username']
    job_details['web_service_password'] = config['service_password']
    if not jenkins.create_job(job, job_details, None):
        raise RuntimeError("Jenkins job creation failure %s" % job)


def get_pipelines_for_dashboard():
    '''
        Get all pipelines available for displaying in dashboard
    '''
    database = connect_db()
    pipeline_documents = Database.get_documents_by_type(
        database, doc_type='project')
    pipelines_data = list()
    jenkins_obj = connect_jenkins()
    for pipeline in pipeline_documents:
        last_build_status = jenkins_obj.get_last_build_status(
            job_name=pipeline['name'])
        scm, jenkins = "dummy-url", "dummy-url"
        if 'scm_url' in pipeline:
            scm = pipeline['scm_url']
        if 'jenkins_url' in pipeline:
            kube = KubernetesAPI()
            external_url = kube.get_service_url('build-at-scale-jenkins')
            jenkins = "http://%s/job/%s" % (external_url, pipeline['name'])
        pipelines_data.append({'pipeline_name': pipeline['name'],
                               'scm_url': scm,
                               'jenkins_url': jenkins,
                               'last_build': last_build_status})
    return pipelines_data


def get_pipelines():
    '''
        Get all pipelines available
    '''
    database = connect_db()
    pipeline_documents = Database.get_documents_by_type(
        database, doc_type='project')
    pipelines = list()
    for pipeline in pipeline_documents:
        pipelines.append(pipeline['name'])
    return pipelines


def get_git_projects():
    '''
        Get all GIT projects for this instance
    '''
    config_document = get_db_config()
    url = config_document['scm_url'] + '/rest/api/1.0/projects'
    headers = {'Content-Type': 'application/json'}
    if 'scm_user' in config_document and 'scm_pass' in config_document:
        response = requests.get(url,
                                auth=(config_document['scm_user'],
                                      config_document['scm_pass']),
                                headers=headers)
    else:
        response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    return data['values']


def get_git_repos(project_key):
    '''
        Get all GIT projects for this instance
    '''
    config_document = get_db_config()
    url = config_document['scm_url'] + \
        '/rest/api/1.0/projects/' + project_key + '/repos'
    headers = {'Content-Type': 'application/json'}
    if 'scm_user' in config_document and 'scm_pass' in config_document:
        response = requests.get(url,
                                auth=(config_document['scm_user'],
                                      config_document['scm_pass']),
                                headers=headers)
    else:
        response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    return data['values']


def get_git_branches(project_key, repo_name):
    '''
        Get all GIT projects for this instance
    '''
    config_document = get_db_config()
    url = config_document['scm_url'] + '/rest/api/1.0/projects/' + \
        project_key + '/repos/' + repo_name + '/branches'
    headers = {'Content-Type': 'application/json'}
    if 'scm_user' in config_document and 'scm_pass' in config_document:
        response = requests.get(url,
                                auth=(config_document['scm_user'],
                                      config_document['scm_pass']),
                                headers=headers)
    else:
        response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    return data['values']


def modify_ssl_for_volume(volume, ssl):
    '''
        Apply ssl to volume
    '''
    config_document = get_db_config()
    ontap_instance = OntapService(config_document['ontap_api'],
                                  config_document['ontap_apiuser'],
                                  config_document['ontap_apipass'],
                                  config_document['ontap_svm_name'],
                                  config_document['ontap_aggr_name'],
                                  config_document['ontap_data_ip'])
    ontap_instance.modify_volume_ssl(volume, ssl)


def setup_ontap_zapi(params, vserver=None):
    hostname = params['hostname']
    username = params['username']
    password = params['password']

    if HAS_NETAPP_LIB:
        # set up zapi
        server = zapi.NaServer(hostname)
        server.set_username(username)
        server.set_password(password)
        if vserver is None:
            vserver = get_cserver(server)
        server.set_vserver(vserver)
        # Todo : Replace hard-coded values with configurable parameters.
        server.set_api_version(major=1, minor=21)
        server.set_port(80)
        server.set_server_type('FILER')
        server.set_transport_type('HTTP')
        return server
    else:
        raise RuntimeError("The python NetApp-Lib module is required")


def get_cserver(server):
    vserver_info = zapi.NaElement('vserver-get-iter')
    query_details = zapi.NaElement.create_node_with_children(
        'vserver-info', **{'vserver-type': 'admin'})
    query = zapi.NaElement('query')
    query.add_child_elem(query_details)
    vserver_info.add_child_elem(query)
    result = server.invoke_successfully(vserver_info,
                                        enable_tunneling=False)
    attribute_list = result.get_child_by_name('attributes-list')
    vserver_list = attribute_list.get_child_by_name('vserver-info')
    return vserver_list.get_child_content('vserver-name')


def autosupport(vol_name, vol_size):
    server = setup_ontap_zapi(
        {'username': 'admin', 'password': 'netapp1!', 'hostname': '10.193.77.37'}, 'ansible_test')
    api = zapi.NaElement('ems-autosupport-log')
    # Host name invoking the API.
    api.add_new_child("computer-name", "BuildAtScale")
    # ID of event. A user defined event-id, range [0..2^32-2].
    api.add_new_child("event-id", "123")
    # Name of the application invoking the API.
    api.add_new_child("event-source", "create_pipeline")
    # Version of application invoking the API.
    api.add_new_child("app-version", "1.1")
    # Application defined category of the event.
    api.add_new_child("category", "Information")
    # Description of event to log. An application defined message to log.
    # if state is 'pipeline-create':
    api.add_new_child("event-description", "A Jenkins pipeline and an ONTAP volume: " + vol_name
                      + " of size " + str(vol_size) + " has been created")
    # Log level. Accepted values are 0 for 'emergency', 1 for 'alert', 2 for 'critical', 3 for 'error', 4 for 'warning', 5 for 'notice', 6 for 'info', and 7 for 'debug'. As of Data ONTAP 9.0, log-level's 2 and 4 are no longer supported. Specifying 2 or 4 would be equivalent to specifying 3 or 5, respectively.
    api.add_new_child("log-level", "6")
    # If 'true', an AutoSupport message will be generated.
    api.add_new_child("auto-support", "false")
    server.invoke_successfully(api, True)


def get_services():
    '''
        Get information about all services associated with Build@Scale
    '''
    config_document = get_db_config()
    kube = KubernetesAPI()
    services = []
    # Retrieve scm service
    scm_service_name = "build-at-scale-%s" % (config_document['scm_type'])
    scm_service_url = "http://%s" % kube.get_service_url(scm_service_name)
    services.append(
        {'name': config_document['scm_type'], 'type': 'scm', 'url': scm_service_url})
    # Retrieve registry service
    registry_service_name = "build-at-scale-%s" % (
        config_document['registry_type'])
    registry_service_url = "http://%s" % kube.get_service_url(
        registry_service_name)
    services.append(
        {'name': config_document['registry_type'], 'type': 'registry', 'url': registry_service_url})
    # Retrieve ci service
    jenkins_service_name = "build-at-scale-jenkins"
    jenkins_service_url = "http://%s" % kube.get_service_url(
        jenkins_service_name)
    services.append({'name': 'jenkins', 'type': 'ci',
                     'url': jenkins_service_url})
    # Retrieve database service
    database_service_name = "build-at-scale-couchdb"
    database_service_url = "http://%s" % kube.get_service_url(
        database_service_name)
    services.append({'name': 'couchdb', 'type': 'database',
                     'url': database_service_url})
    # Retrieve ontap nslm information (this is not a kubernetes service)
    services.append({'name': 'ontap', 'type': 'storage', 'name': 'ontap',
                     'url': "https://%s" % config_document['ontap_api']})
    logging.error(services)
    return services

def get_workspaces():
    '''
        Get information about all workspaces associated with Build@Scale
    '''
    db = connect_db()

    try:
        workspaces = Database.get_documents_by_type(db,'workspace')
    except Exception as e:
        logging.error("Unable to retrieve workspace documents from database: %s" %
              traceback.format_exc())
        workspaces=[]
    return workspaces

def delete_workspace(name):
    '''

    '''
    try:
        config = get_db_config()
        db = connect_db()
        ontap = OntapService(config['ontap_api'], config['ontap_apiuser'], config['ontap_apipass'], config['ontap_svm_name'], config['ontap_aggr_name'], config['ontap_data_ip'])
        ontap.delete_volume(name)
        workspace = Database.get_document_by_name(db,name)
        pod_name = workspace['pod_name']
        db.delete(workspace)
        kube = KubernetesAPI()
        kube.delete_pod(pod_name)

    except Exception as e:
        logging.error("Unable to delete workspace!: %s" %
              traceback.format_exc())
        raise

def delete_project(name):
    '''
    Delete all elements associated with a given project/pipeline(ontap volume/jenkins job)
    '''
    try:
        config = get_db_config()
        db = connect_db()
        project = Database.get_document_by_name(db,name)
        volume = project['volume']
        ontap = OntapService(config['ontap_api'], config['ontap_apiuser'], config['ontap_apipass'], config['ontap_svm_name'], config['ontap_aggr_name'], config['ontap_data_ip'])
        ontap.delete_volume(volume)
        db.delete(project)
        jenkins = connect_jenkins()
        jenkins.delete_job(name)

    except Exception as e:
        logging.error("Unable to delete project!: %s" %
              traceback.format_exc())
        raise

def setup_required(f):
    @wraps(f)
    def setup(*args, **kwargs):
        # Configure the couchdb cluster
        headers = {'Content-type': 'application/json'}
        db_cluster_config = {"action": "enable_cluster", "bind_address": "0.0.0.0",
                             "username": "admin", "password": "admin", "node_count": "1"}
        try:
            r = requests.post("http://%s/_cluster_setup" %
                              app.config['DATABASE_URL'], json=db_cluster_config, headers=headers)

        except Exception as exc:
            raise GenericException(
                500, "Error configuring the couchdb cluster : %s, please contact your administrator" % str(exc))

        # Retrieve customer configuration document from database
        database = connect_db()
        config_document = get_db_config()
        if not config_document:
            raise GenericException(500,
                                   "Customer config doc not found, please contact your administrator",
                                   "Database Exception")

        # Populate configuration document with ontap information

        config_document['ontap_api'] = app.config['ONTAP_API']
        config_document['ontap_apiuser'] = app.config['ONTAP_APIUSER']
        config_document['ontap_apipass'] = app.config['ONTAP_APIPASS']
        config_document['ontap_svm_name'] = app.config['ONTAP_SVM_NAME']
        config_document['ontap_aggr_name'] = app.config['ONTAP_AGGR_NAME']
        config_document['ontap_data_ip'] = app.config['ONTAP_DATA_IP']
        config_document['scm_type'] = app.config['SCM_TYPE']
        config_document['scm_url'] = "build-at-scale-%s.default" % config_document['scm_type']
        config_document['registry_type'] = app.config['REGISTRY_TYPE']
        config_document['service_type'] = app.config['SERVICE_TYPE']
        config_document.store(database)
        return f(*args, **kwargs)
    return setup
