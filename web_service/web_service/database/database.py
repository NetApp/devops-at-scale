''' Wrapper Module for accessing couchdb database'''
import couchdb
from .configuration import Configuration
from .user import User

def connect(url, user, password, database):
    '''Connect to existing couchdb database or create it'''
    couchdb_server = couchdb.Server("http://%s:%s@%s" % (user, password, url))
    if database in couchdb_server:
        return couchdb_server[database]
    return create(url, user, password, database)

def create(url, user, password, database_name):
    '''Create a couchdb database'''
    couchdb_server = couchdb.Server("http://%s:%s@%s" % (user, password, url))
    database = couchdb_server.create(database_name)
    # create default view needed to query data
    create_view(database, view_name='get_documents_by_name',
                view_method='''function(doc) {
                                    emit(doc.name, doc.type);
                                }''')
    create_view(database, view_name='get_documents_by_type',
                view_method='''function(doc) {
                                    emit(doc.type, doc.name);
                                }''')
    create_view(database, view_name='get_snapshots_by_volume',
                view_method='''function(doc) {
                                    if(doc.type == 'snapshot') {
                                        emit(doc.volume, doc.name);
                                    }
                                }''')
    create_view(database, view_name='get_workspaces_by_project',
                view_method='''function(doc) {
                                    if(doc.type == 'workspace') {
                                        emit(doc.project, doc.workspace);
                                    }
                                }''')
    create_view(database, view_name='get_workspaces_by_uid',
                view_method='''function(doc) {
                                    if(doc.type == 'workspace') {
                                        emit(doc.uid, doc.name);
                                    }
                                }''')
    # create a configuration document with default values
    new_configuration = Configuration(name='configuration')
    new_configuration.store(database)
    # create a default user for demonstration purposes
    default_user = User(name='admin',uid=3,gid=3,email='admin@netapp.com')
    default_user.store(database)
    return database

def create_view(database, view_name, view_method):
    '''Create a view'''
    view = couchdb.design.ViewDefinition('design_doc', view_name, view_method)
    view.get_doc(database)
    view.sync(database)

def delete(url, user, password, database):
    '''Delete a couchdb database'''
    couchdb_server = couchdb.Server("http://%s:%s@%s" % (user, password, url))
    if database in couchdb_server:
        del couchdb_server[database]


def get_document_by_name(database, document):
    '''Get a document by it's name'''
    for item in database.view('design_doc/get_documents_by_name', key=document, limit=1):
        document = couchdb.mapping.Document.load(database, item.id)
        return document

def get_documents_by_type(database, doc_type):
    '''Get list of documents by it's type
    @return: list of documents where each doc is formatted as a dict of all available fields'''
    documents = list()
    results = database.view('design_doc/get_documents_by_type', key=doc_type)
    for item in results:
        documents.append(couchdb.mapping.Document.load(database, item.id))
    return documents

def get_snapshots_by_volume(database, volume):
    '''Get all snapshot documents that belong to volume
       @return: ViewResults where each row has row.key=volume and row.value=snapshot'''
    return database.view('design_doc/get_snapshots_by_volume', key=volume)

def get_workspaces_by_project(database, project):
    '''Get all workspace documents that belong to a project
       @return: ViewResults where each row has row.key=volume \
                and row.value=workspace_name(clone_name)'''
    return database.view('design_doc/get_workspaces_by_project', key=project)

def get_workspaces_by_user(database, uid):
    '''Get all snapshot documents that belong to volume
       @return: list of workspace_names owned by uid'''
    workspaces = list()
    for item in database.view('design_doc/get_workspaces_by_uid', key=uid):
        workspaces.append(item.value)
    return workspaces
