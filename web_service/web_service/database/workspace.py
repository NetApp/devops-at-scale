''' workspace couchdb document mapping '''
import logging
from datetime import datetime
from couchdb.mapping import Document, TextField, DateTimeField, IntegerField
import web_service.database.database as Database
import web_service.helpers.helpers as helpers
from web_service.ontap.ontap_service import OntapService


class Workspace(Document):
    '''Class for handling workspace documents in db'''
    name = TextField()
    clone = TextField()
    mount = TextField()
    type = TextField(default="workspace")
    pipeline = TextField()
    build_name = TextField()
    pvc = TextField()
    source_pvc = TextField()
    service = TextField()
    pod = TextField()
    pv = TextField()
    uid = IntegerField()
    gid = IntegerField()
    username = TextField()
    creation_date = DateTimeField(default=datetime.now)
    source_workspace_pvc = TextField()
    ide_url = TextField()


def purge_old_workspaces():
    """
    Purge workspaces older than X days
    @return: count of workspaces deleted
    """
    database = helpers.connect_db()
    config = helpers.get_db_config()
    projects_in_db = Database.get_documents_by_type(database, doc_type='project')
    if not projects_in_db:
        return 0
    count = 0
    deleted_workspaces = list()
    for project in projects_in_db:
        workspaces_in_project = Database.get_workspaces_by_project(database, project=project['name'])
        for workspace in workspaces_in_project:
            # ontap doesn't provide last_access_timestamp for volumes
            # hence, snapdiff latest snapshot with snapshot X days older \
            # to find if workspace is active
            ontap = OntapService(config['ontap_api'], config['ontap_apiuser'], config['ontap_apipass'],
                                 config['ontap_svm_name'], config['ontap_aggr_name'], config['ontap_data_ip'])
            deleted, error = ontap.get_snapdiff_and_delete(
                volume_name=workspace.value,
                count=project['workspace_purge_limit'])

            # delete inconsistent or old workspace that exceeded purge limit
            if error is not None or deleted is True:
                workspace_doc = Database.get_document_by_name(database, workspace.value)
                database.delete(workspace_doc)
                deleted_workspaces.append(workspace.value)
                logging.info("Purge: deleted workspace %s from DB", workspace.value)
                count += 1
    return count, deleted_workspaces


def exceeded_workspace_count_for_user(username, limit):
    '''Verify if user has exceeded workspace limit'''
    database = helpers.connect_db()
    workspaces = Database.get_workspaces_by_user(database, user=username)
    if len(workspaces) >= limit:
        return True, workspaces
    return False, workspaces
