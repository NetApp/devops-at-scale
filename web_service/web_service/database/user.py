''' workspace couchdb document mapping '''
import logging
from datetime import datetime
from couchdb.mapping import Document, TextField, DateTimeField, IntegerField

class User(Document):
    '''Class for handling workspace documents in db'''
    name = TextField()
    type = TextField(default="user")
    email =  TextField()
    uid = IntegerField()
    gid = IntegerField()
    creation_date = DateTimeField(default=datetime.now)
