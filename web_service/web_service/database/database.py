''' Wrapper Module for accessing couchdb database'''
import couchdb
import re
from .configuration import Configuration
from .user import User


def connect(url, user, password, database):
    '''Connect to existing couchdb database or create it'''
    host = url
    if url.startswith('http'):
        host = re.sub(r'https?://', '', url)
    if url.startswith('www.'):
        host = re.sub(r'www.', '', url)
    server = "http://%s:%s@%s"
    couchdb_server = couchdb.Server("http://%s:%s@%s" % (user, password, host))
    if database in couchdb_server:
        return couchdb_server[database]
    return create(host, user, password, database)


def create(host, user, password, database_name):
    '''Create a couchdb database'''

    couchdb_server = couchdb.Server("http://%s:%s@%s" % (user, password, host))
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
    create_view(database, view_name='get_build_clones_with_status_by_volume',
                view_method='''function(doc) {
                                        if(doc.type == 'snapshot') {
                                            emit(doc.volume, doc.name+'_'+doc.build_status);
                                        }
                                    }''')
    create_view(database, view_name='get_workspaces_by_username',
                view_method='''function(doc) {
                                            if(doc.type == 'workspace') {
                                                emit(doc.username, doc.name);
                                            }
                                        }''')
    create_view(database, view_name='get_build_clones_by_pipeline',
                view_method='''function(doc) {
                                               if(doc.type == 'snapshot') {
                                                   emit(doc.parent_pipeline_pvc, doc.pvc);
                                               }
                                           }''')
    create_view(database, view_name='get_ws_clones_by_pipeline',
                view_method='''function(doc) {
                                               if(doc.type == 'workspace') {
                                                   emit(doc.pipeline_pvc, doc.pvc);
                                               }
                                           }''')
    # create a configuration document with default values
    new_configuration = Configuration(name='configuration')
    new_configuration.store(database)
    # create a default user for demonstration purposes
    default_user = User(name='admin', uid=1000, gid=1000, email='admin@netapp.com')
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


def get_workspaces_by_user(database, user):
    '''Get all snapshot documents that belong to volume
       @return: list of workspace_names owned by user'''
    workspaces = list()
    if user.isdigit():
        for item in database.view('design_doc/get_workspaces_by_uid', key=user):
            workspaces.append(item.value)
    else:
        for item in database.view('design_doc/get_workspaces_by_username', key=user):
            workspaces.append(item.value)
    return workspaces


def get_build_clones_with_status_by_volume(database, volume):
    '''Get all clone names associated with a volume
       @return: ViewResults where each row has row.key=volume and row.value=clone_name_build_status'''
    return database.view('design_doc/get_build_clones_with_status_by_volume', key=volume)


def get_build_clones_by_pipeline(database, pipeline_pvc):
    '''Get all build clone PVCs associated with a pipeline
       @return: ViewResults where each row has row.key=pvc and row.value=build_clone_pvc'''
    return database.view('design_doc/get_build_clones_by_pipeline', key=pipeline_pvc)


def get_ws_clones_by_pipeline(database, pipeline_pvc):
    '''Get all workspace clone PVCs associated with a pipeline
       @return: ViewResults where each row has row.key=pvc and row.value=ws_clone_pvc'''
    return database.view('design_doc/get_ws_clones_by_pipeline', key=pipeline_pvc)
