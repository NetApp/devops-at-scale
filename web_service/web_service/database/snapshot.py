''' snapshot couchdb document mapping '''
import logging
from datetime import datetime
from couchdb.mapping import Document, TextField, DateTimeField, IntegerField
from web_service.helpers import helpers
from web_service.ontap.ontap_service import OntapService
import web_service.database.database as Database


class Snapshot(Document):
    '''Class for handling snapshot documents in db'''
    name = TextField()
    type = TextField(default="snapshot")
    volume = TextField()
    project = TextField()
    jenkins_build = IntegerField()
    build_status = TextField()
    creation_date = DateTimeField(default=datetime.now)


# Module methods: clients using these methods donot need a Snapshot Document instance
def purge(snapshot_type):
    """
    Purge SCM or CI snapshots
    @param snapshot_type: snapshot-type (SCM or CI)
    @return: count of snapshots purged
    """
    config = helpers.get_db_config()
    if snapshot_type == "scm":
        volume = config['scm_volume']
        purge_limit = config['scm_purge_limit']
        purge_inconsistent_snapshots(volume)
        count = purge_snapshots_by_volume(volume, purge_limit)
    elif snapshot_type == "ci":
        count = purge_ci_snapshots()
    return count


def purge_inconsistent_snapshots(volume):
    """
    Snapshot consistency check - ONTAP vs DB
    Purge inconsistent snapshot documents from DB
    i.e. snapshots in DB that do not exist in ONTAP
    @return: count of snapshots deleted from DB
    """
    config = helpers.get_db_config()
    database = helpers.connect_db()
    snapshots_in_db = Database.get_snapshots_by_volume(database, volume=volume)
    ontap = OntapService(config['ontap_api'], config['ontap_apiuser'], config['ontap_apipass'],
                         config['ontap_svm_name'], config['ontap_aggr_name'], config['ontap_data_ip'])
    ontap_snapshot_data = ontap.get_snapshot_list(volume)
    if not ontap_snapshot_data:
        # purge all snapshots from DB and return:
        return purge_snapshots_from_db(snapshots_ontap=[],
                                       snapshots_db=snapshots_in_db)
    if not snapshots_in_db:
        # return if there are no snapshot documents in db
        return 0

    ontap_snapshots = [snap['snapshot_name'] for snap in ontap_snapshot_data]
    return purge_snapshots_from_db(snapshots_ontap=ontap_snapshots,
                                   snapshots_db=snapshots_in_db)


def purge_snapshots_from_db(snapshots_ontap, snapshots_db):
    ''' purge snapshots present only in snapshot_db but not in snapshots_ontap'''
    database = helpers.connect_db()
    count = 0
    # snapshots_db is a list of rows:
    # where each row has row.key=volume_name and row.value=snapshot_name
    for snap in snapshots_db:
        if snap.value not in snapshots_ontap:
            count += 1
            database.delete(snap)
            logging.info("Purge: inconsistent snapshot %s deleted from db", snap.value)
    return count


def purge_snapshots_by_volume(volume, purge_limit):
    """
    Purge snapshots per volume
    @return: count of snapshots purged
    """
    config = helpers.get_db_config()
    ontap = OntapService(config['ontap_api'], config['ontap_apiuser'], config['ontap_apipass'],
                         config['ontap_svm_name'], config['ontap_aggr_name'], config['ontap_data_ip'])
    ontap_snapshot_list = ontap.get_snapshot_list(volume)

    if ontap_snapshot_list is None:
        return 0

    delete_count = len(ontap_snapshot_list) - purge_limit

    if delete_count <= 0:
        return 0

    database = helpers.connect_db()

    sorted_by_timestamp = sorted(ontap_snapshot_list, key=lambda snap: snap['timestamp'])
    delete_snapshot_list = sorted_by_timestamp[:delete_count]
    for snap in delete_snapshot_list:
        status = ontap.delete_snapshot(volume, snap['snapshot_name'])
        if helpers.verify_successful_response(status):
            # delete snapshot document from db
            doc = Database.get_document_by_name(database, snap['snapshot_name'])
            if not doc:  # if snapshot to be deleted is not found in DB
                logging.info("Purge: snapshot document not found for %s", snap['snapshot_name'])
            else:
                database.delete(doc)
                logging.info("Purge: snapshot deleted from DB and ONTAP: %s",
                             snap['snapshot_name'])
    return delete_count


def purge_ci_snapshots():
    """
    Purge CI snapshots
    @return: count of CI snapshots purged
    """
    database = helpers.connect_db()
    # Get all active projects
    projects_in_db = Database.get_documents_by_type(database, doc_type="project")
    if not projects_in_db:
        return 0
    count = 0
    # For each project, get all snapshot documents
    for project in projects_in_db:
        purge_inconsistent_snapshots(volume=project['volume'])
        count += purge_snapshots_by_volume(project['volume'], project['ci_purge_limit'])
    return count
