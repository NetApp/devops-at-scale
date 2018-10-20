'''Test views.py'''
import json
import os
import sys
import unittest
from unittest.mock import patch, Mock
from web_service import create_app
from web_service.helpers.errors import GenericException

# Set project root directory so coverage.py can generate coverage
BASE_DIR = os.path.join(os.path.dirname(__file__), '../..')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class ViewsTestCase(unittest.TestCase):
    '''Test cases for routes in views.py'''
    def setUp(self):
        self.app = create_app()
        with self.app.app_context():
            self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        pass

    def test_index(self):
        ''' Test index response '''
        response = self.client.get("/")
        # assert the status code of the response
        self.assertEqual(response.status_code, 200)

    def test_index_backend(self):
        ''' Test index response with endpoint 'backend' '''
        response = self.client.get("/backend/")
        # assert the status code of the response
        self.assertEqual(response.status_code, 200)

    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_snapshot_list(self, mock_get_snapshot_list):
        ''' Test list snapshots endpoint '''
        mock_get_snapshot_list.return_value = ["test_snapshot_name_1"], None
        response = self.client.get("/backend/test_demo/snapshots")
        data = json.loads(response.data)    #convert response from bytes to JSON
        # response contains list of snapshot names
        self.assertEqual(mock_get_snapshot_list.return_value[0], data)
        self.assertEqual(response.status_code, 200)

    @patch('web_service.ontap.ontap_service.OntapService.create_snapshot')
    def test_snapshot_create(self, mock_create_snapshot):
        ''' Test create snapshot endpoint '''
        snapshot_name = 'test_create_snapshot'
        mock_create_snapshot.return_value = [
            {
                "code": 201,
                "error_message": "",
                "message": "Snapshot %s completed successfully" %snapshot_name,
                "resource": "Snapshot",
                "resource_name": snapshot_name,
                "status": "COMPLETED"
            }
        ]
        response = self.client.post("/backend/snapshot/create",
                                    data=dict(volume_name='test_volume',
                                              snapshot_name=snapshot_name))
        data = json.loads(response.data)[0]    #response is single JSON object enclosed in a list
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['resource_name'], snapshot_name)

    @patch('web_service.ontap.ontap_service.OntapService.delete_snapshot')
    def test_snapshot_delete(self, mock_delete_snapshot):
        ''' Test delete snapshot endpoint '''
        snapshot_name = 'test_create_snapshot'
        mock_delete_snapshot.return_value = [
            {
                "code": 201,
                "error_message": "",
                "message": "Snapshot %s completed successfully" %snapshot_name,
                "resource": "Snapshot",
                "resource_name": snapshot_name,
                "status": "COMPLETED"
            }
        ]
        response = self.client.delete("/backend/snapshot/delete",
                                      data=dict(volume_name='test_volume',
                                                snapshot_name=snapshot_name))
        data = json.loads(response.data)[0]    #response is single JSON object enclosed in a list
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['resource_name'], snapshot_name)

    @patch('web_service.ontap.ontap_service.OntapService.create_snapshot')
    def test_snapshot_bad_request(self, mock_create_snapshot):
        ''' Test POST without body for response 400 '''
        mock_create_snapshot.return_value = [
            {
                "code": 201,
                "error_message": "",
                "message": "Snapshot test_snapshot_bad_request completed successfully",
                "resource": "Snapshot",
                "resource_name": "test_snapshot_bad_request",
                "status": "COMPLETED"
            }
        ]
        response = self.client.post("/backend/snapshot/create", data=None)
        self.assertEqual(response.status_code, 400)

    @patch('web_service.jenkins.jenkins_api_secure.j.jenkins.Jenkins')
    @patch('web_service.helpers.helpers.get_db_config')
    @patch('web_service.ontap.ontap_service.OntapService.create_volume')
    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.create_pv_and_pvc')
    @patch('web_service.jenkins.jenkins_api_secure.JenkinsAPI.create_job')
    def test_project_creation(self, mock_jenkins_api, mock_kubernetes_api,
                              mock_create_volume, mock_db_connect, mock_jenkins):
        '''Test project creation endpoint'''
        mock_db_connect.return_value = {'jenkins_url':'', 'jenkins_user':'',
                                        'jenkins_pass':'', 'git_volume':'',
                                        'service_username': '', 'service_password':'',
                                        'web_service_url': '', 'container_registry': ''}
        mock_jenkins_api.return_value = True
        mock_create_volume.return_value = [
            {'code': 201, 'resource': 'Volume',
             'resource_name': 'test_vol', 'error_message': 'CREATED'}
        ], "600"
        mock_kubernetes_api.return_value = [
            {
                'resource_name': 'test-1-pv', 'status': 'COMPLETED', 'code': 201,
                'message': 'PV test-1-pv created successfully', 'error': '', 'resource': 'PV'
            },
            {
                'resource_name': 'test-1-pvc', 'status': 'COMPLETED', 'code': 201,
                'message': 'PVC test-1-pvc created successfully', 'error': '', 'resource': 'PVC'
            }
        ]
        new_project_data = {
            'scm-url': 'https://test@example.net/user/my-new-project.git',
            'scm-branch': 'master',
        }
        resp = self.client.post(
            "/backend/project/create", data=new_project_data)
        self.assertEqual(resp.status_code, 200)

    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.create_pv_and_pvc_and_pod')
    @patch('web_service.ontap.ontap_service.OntapService.create_clone')
    def test_workspace_creation(self, mock_create_clone, mock_create_pv_pvc_pod):
        '''Test workspace creation endpoint'''
        mock_create_clone.return_value = [
            {'code': 201, 'resource': 'Clone', 'status': 'COMPLETED',
             'resource_name': 'test_clone', 'message': 'Clone test_clone completed successfully'}
        ], "1000"
        mock_create_pv_pvc_pod.return_value = [
            {'code': 201, 'resource': 'PV', 'status': 'COMPLETED',
             'resource_name': 'test-clone-pv',
             'message': 'PV test-clone-pv completed successfully'},
            {'code': 201, 'resource': 'PVC', 'status': 'COMPLETED',
             'resource_name': 'test-clone-pvc',
             'message': 'PV test-clone-pv completed successfully'},
            {'code': 201, 'resource': 'Pod', 'status': 'COMPLETED',
             'resource_name': 'test-clone-pod',
             'message': 'PV test-clone-pod completed successfully'}
        ]
        new_workspace_data = {
            'workspace_name' : 'test',
            'snapshot_name' : 'test_snapshot',
            'uid' : 1000,
            'gid' : 1000
        }
        response = self.client.post("/backend/workspace/create", data=new_workspace_data)
        self.assertEqual(response.status_code, 200)

    @patch('web_service.helpers.helpers.get_db_config')
    @patch('web_service.database.snapshot.Snapshot')
    @patch('web_service.database.snapshot.purge')
    def test_snapshot_purge(self, mock_snapshot_purge, mock_snapshot, mock_db_connect):
        '''Test snapshots purge endpoint'''
        response = self.client.post("/backend/snapshot/purge")
        self.assertEqual(response.status_code, 200)

    @patch('web_service.helpers.helpers.get_db_config')
    @patch('web_service.database.snapshot.Snapshot')
    @patch('web_service.database.snapshot.purge')
    def test_snapshot_purge_fail(self, mock_snapshot_purge, mock_snapshot, mock_db_connect):
        '''Test snapshots purge exception'''
        response = self.client.post("/backend/snapshot/purge", data={'type': 'invalid'})
        self.assertEqual(response.status_code, 406)

    @patch('web_service.database.workspace.purge_old_workspaces')
    def test_workspace_purge(self, mock_purge_workspace):
        '''Test purge workspaces endpoint'''
        mock_purge_workspace.return_value = 1, ['deleted_ws_1']
        response = self.client.post("/backend/workspace/purge")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['purged_workspaces']), 1)

    @patch('web_service.database.workspace.exceeded_workspace_count_for_user')
    @patch('web_service.helpers.helpers.get_db_config')
    @patch('web_service.helpers.helpers.connect_db')
    def test_exception_workspace_limit(self, mock_connect_db, mock_get_db,
                                       mock_exceeded_limit):
        '''Test exception when user exceeds workspace limit'''
        workspace_data = {
            'workspace_name' : 'test',
            'snapshot_name' : 'test_snapshot',
            'uid' : 1234,
            'gid' : 1234
        }
        mock_exceeded_limit.return_value = True, None
        response = self.client.post("/backend/workspace/create", data=workspace_data)
        self.assertEqual(response.status_code, 401)

if __name__ == "__main__":
    unittest.main()
