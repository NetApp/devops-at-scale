'''Snapshot document tests'''
import unittest
from unittest.mock import patch, Mock
from web_service import create_app
import web_service.database.workspace as workspace

class TestWorkspace(unittest.TestCase):
    '''Test snapshot document class'''
    def setUp(self):
        app_settings = 'config.TestingConfig'
        self.app = create_app()
        self.app.config.from_object(app_settings)
        with self.app.app_context():
            self.app.testing = True

    def tearDown(self):
        pass

    @patch('web_service.helpers.helpers.connect_db')
    @patch('web_service.database.database.get_documents_by_type')
    @patch('web_service.database.database.get_workspaces_by_project')
    @patch('web_service.ontap.ontap_service.OntapService.get_snapdiff_and_delete')
    def test_purge_old_workspaces(self, mock_delete_clone, mock_get_workspaces,
                                  mock_get_projects, mock_connect_db):
        '''Test purge workspace > purge_limit'''
        mock_get_projects.return_value = [{"name": "proj_1", "workspace_purge_limit": 1},
                                          {"name": "proj_2", "workspace_purge_limit": 2}]
        mock_get_workspaces.side_effect = [
            [Mock(value='proj_1_ws_1'), #for proj_1 => return 2 workspaces
             Mock(value='proj_1_ws_2')],
            [Mock(value='proj_2_ws_1')] #for proj_2 => return 1 workspace
            ]
        mock_delete_clone.side_effect = [(True, None),  #proj_1_ws_1
                                         (False, None), #proj_1_ws_2
                                         (True, None)]  #proj_2_ws_1
        count, workspaces = workspace.purge_old_workspaces()
        self.assertEqual(count, 2)
        self.assertEqual(workspaces, ['proj_1_ws_1', 'proj_2_ws_1'])

    @patch('web_service.helpers.helpers.connect_db')
    @patch('web_service.database.database.get_workspaces_by_user')
    def test_workspace_count_exceeded(self, mock_get_workspaces, mock_connect_db):
        mock_get_workspaces.return_value = [
            'ws_1',
            'ws_2',
            'ws_3'
            ]
        negative, ws_list = workspace.exceeded_workspace_count_for_user('1000', 10)
        positive, ws_list = workspace.exceeded_workspace_count_for_user('1000', 3)
        self.assertEqual(negative, False)
        self.assertEqual(positive, True)
        self.assertEqual(ws_list, mock_get_workspaces.return_value)
