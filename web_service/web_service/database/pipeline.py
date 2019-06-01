''' project couchdb document mapping '''
from datetime import datetime
from couchdb.mapping import Document, TextField, DateTimeField, IntegerField


class Pipeline(Document):
    '''Class for handling project documents in db'''
    name = TextField()
    type = TextField(default="project")
    volume = TextField()
    scm_url = TextField()
    jenkins_url = TextField()
    workspace_purge_limit = IntegerField(default=21)
    creation_date = DateTimeField(default=datetime.now)
    ci_purge_limit = IntegerField(default=50)
    export_policy = TextField()
    pvc = TextField()
