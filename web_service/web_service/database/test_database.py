'''Test database.py'''
import os
import sys
import unittest
from web_service import create_app
import web_service.database.database as Database
from web_service.database.project import Project
from web_service.helpers import helpers

# Set project root directory so coverage.py can generate coverage
BASE_DIR = os.path.join(os.path.dirname(__file__), '../..')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class TestDatabase(unittest.TestCase):
    '''Test database module methods'''
    def setUp(self):
        app_settings = 'config.TestingConfig'
        self.app = create_app()
        self.app.config.from_object(app_settings)
        with self.app.app_context():
            self.app.testing = True

    def tearDown(self):
        pass

    def test_database_create(self):
        ''' Test if database creation is successful'''
        dbname = "test_database_create_" + helpers.return_random_string(4)
        database = Database.connect(self.app.config['DATABASE_URL'], self.app.config[
            'DATABASE_USER'], self.app.config['DATABASE_PASSWORD'], dbname)
        if not database:
            self.fail("Could not connect to database %s " % dbname)
        Database.delete(self.app.config['DATABASE_URL'], self.app.config[
            'DATABASE_USER'], self.app.config['DATABASE_PASSWORD'], dbname)

    def test_document_create(self):
        ''' Test if document creation is successful'''
        dbname = "test_database_create_" + helpers.return_random_string(4)
        database = Database.connect(self.app.config['DATABASE_URL'], self.app.config[
            'DATABASE_USER'], self.app.config['DATABASE_PASSWORD'], dbname)
        new_project = Project(name="project_%s" %
                              helpers.return_random_string(4))
        new_project.store(database)
        if not Project.load(database, new_project.id):
            self.fail("Document %s not created successfully " % new_project.id)
        Database.delete(self.app.config['DATABASE_URL'], self.app.config[
            'DATABASE_USER'], self.app.config['DATABASE_PASSWORD'], dbname)

if __name__ == "__main__":
    unittest.main()