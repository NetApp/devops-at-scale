''' configuration couchdb document mapping '''
from couchdb.mapping import Document, TextField, IntegerField

class Configuration(Document):
    '''Create config document. One configuration per customer'''
    name = TextField()
    type = TextField(default="configuration")
    jenkins_url = TextField(
        default="http://build-at-scale-jenkins.default:8080/")
    jenkins_user = TextField(default="admin")
    jenkins_pass = TextField(default="admin")
    scm_url = TextField(
        default="http://build-at-scale-gitlab.default")
    scm_user = TextField(default="admin")
    scm_pass = TextField(default="admin")
    scm_type = TextField(default="gitlab")
    git_volume = TextField(default="build_at_scale_gitlab")
    scm_purge_limit = IntegerField(default=50)
    container_registry = TextField(
        default="build-at-scale-docker-registry:30450")
    service_username = TextField(default="admin")
    service_password = TextField(default="admin")
    web_service_url = TextField(
        default="http://build-at-scale-webservice.default:80")
    workspace_pod_image = TextField(
        default="theiaide/theia-python:0.4.0-next.6243fc63")
    user_workspace_limit = IntegerField(default=10)
    ontap_api = TextField()
    ontap_apiuser = TextField()
    ontap_apipass = TextField()
    ontap_svm_name = TextField()
    ontap_aggr_name = TextField()
    ontap_data_ip = TextField()
    registry_type = TextField(default="docker-registry")
