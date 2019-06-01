''' configuration couchdb document mapping '''
from couchdb.mapping import Document, TextField, IntegerField


class Configuration(Document):
    """
    Create config document. One configuration per customer
    For release 1.1
    """
    name = TextField()
    type = TextField(default="configuration")

    # ONTAP
    ontap_svm_name = TextField()
    ontap_aggr_name = TextField()
    ontap_data_ip = TextField()

    # SCM
    scm_service_name = TextField()
    scm_pvc_name = TextField()
    scm_url = TextField()
    scm_user = TextField(default="root")
    scm_pass = TextField(default="root_devopsatscale")
    scm_volume = TextField()
    scm_type = TextField(default="gitlab")
    scm_purge_limit = IntegerField(default=50)

    # JENKINS
    jenkins_service_name = TextField()
    jenkins_url = TextField()
    jenkins_user = TextField(default="admin")
    jenkins_pass = TextField(default="admin")

    # Database CouchDB
    database_service_name = TextField()

    # Artifactory
    registry_service_name = TextField()
    registry_type = TextField(default="artifactory")

    # Webservice
    web_service_name = TextField()
    web_service_url = TextField()
    web_service_username = TextField(default="admin")
    web_service_password = TextField(default="admin")

    # Others
    services_type = TextField(default='NodePort')
    devops_at_scale_version = TextField(default='1.1')

    # User Workspace
    workspace_pod_image = TextField(default="theiaide/theia-python:0.4.0-next.6243fc63")
    user_workspace_limit = IntegerField(default=10)
