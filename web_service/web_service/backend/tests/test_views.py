'''Test views.py'''
import json
import os
import sys
import unittest
from unittest.mock import patch, Mock
from web_service import create_app

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

    # TODO: revisit @setup_required in frontend and backend
    @patch('web_service.helpers.helpers._setup_couchdb')
    def test_index(self, mock_setup):
        ''' Test index response '''
        response = self.client.get("/")
        # assert the status code of the response
        self.assertEqual(response.status_code, 200)

    @patch('web_service.helpers.helpers._setup_couchdb')
    def test_index_backend(self, mock_setup):
        ''' Test index response with endpoint 'backend' '''
        response = self.client.get("/backend/")
        # assert the status code of the response
        self.assertEqual(response.status_code, 200)

    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    @patch('web_service.helpers.helpers._setup_couchdb')
    def test_snapshot_list(self, mock_setup, mock_get_snapshot_list):
        ''' Test list snapshots endpoint '''
        mock_get_snapshot_list.return_value = ["test_snapshot_name_1"], None
        # TODO: missing endpoint
        response = self.client.get("/backend/test_demo/snapshots")
        self.assertEqual(response.status_code, 404)
        # data = json.loads(response.data)    # convert response from bytes to JSON
        # response contains list of snapshot names
        # self.assertEqual(mock_get_snapshot_list.return_value[0], data)

    # TODO: revisit @setup_required in frontend and backend
    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.get_instance')
    @patch('web_service.helpers.helpers._setup_couchdb')
    @patch('web_service.helpers.helpers.get_db_config')
    @patch('web_service.helpers.helpers.connect_db')
    @patch('web_service.database.snapshot.Snapshot.store')
    def test_build_snapshot_create(self, mock_snapshot_store, mock_connect_db,
                                   mock_get_db_config, mock_setup, mock_kube):
        ''' Test create volumeclaim endpoint '''
        pvc_clone_name = 'test_pvc_clone_name'
        mock_kube.return_value.create_pvc_clone_resource.return_value = [
            {
                "code": 201,
                "error_message": "",
                "message": "Snapshot %s completed successfully" % pvc_clone_name,
                "resource": "Snapshot",
                "resource_name": pvc_clone_name,
                "status": "COMPLETED"
            }
        ]
        response = self.client.post("/backend/volumeclaim/clone",
                                    data=dict(pvc_clone_name=pvc_clone_name,
                                              pvc_source_name='test_pvc_source_name',
                                              jenkins_build=123,
                                              # TODO: is this used?
                                              volume_name='isthisneeded?',
                                              build_status='passed'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)[0]    # response is single JSON object enclosed in a list
        self.assertEqual(data['resource_name'], pvc_clone_name)

    @patch('web_service.helpers.helpers._setup_couchdb')
    @patch('web_service.helpers.helpers.get_db_config')
    def test_snapshot_bad_request(self, mock_get_db_config, mock_setup):
        ''' Test POST without body for response 400 '''
        response = self.client.post("/backend/volumeclaim/clone", data=None)
        self.assertEqual(response.status_code, 400)

    @patch('web_service.jenkins.jenkins_api_secure.j.jenkins.Jenkins')
    @patch('web_service.helpers.helpers._setup_couchdb')
    @patch('web_service.helpers.helpers.connect_db')            # for _get_config_from_db
    @patch('web_service.helpers.helpers.get_db_config')         # for _get_config_from_db
    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.get_instance')
    @patch('web_service.jenkins.jenkins_api_secure.JenkinsAPI.create_job')
    def test_pipeline_creation(self, mock_jenkins_api, mock_kube,
                               mock_get_db_config, mock_db_connect, mock_setup, mock_jenkins):
        '''Test project creation endpoint'''
        mock_get_db_config.return_value = {'jenkins_url': 'test', 'jenkins_user': 'test',
                                           'jenkins_pass': 'test', 'scm_volume': '',
                                           'web_service_username': '', 'web_service_password': '',
                                           'web_service_url': '', 'registry_service_name': '',
                                           'scm_pvc_name': 'test', 'kube_namespace': 'test'}
        mock_kube.return_value.get_volume_name_from_pvc.return_value = 'test_volume_name'
        mock_jenkins_api.return_value = True
        mock_kube.return_value.create_pvc_resource.return_value = {
            'name': 'test-1-pvc', 'status': 'COMPLETED', 'code': 201,
            'message': 'PVC test-1-pvc created successfully', 'error': '', 'resource': 'PVC'
        }
        new_project_data = {
            'scm-url': 'https://test@example.net/user/my-new-project.git',
            'scm-branch': 'master',
        }
        resp = self.client.post(
            "/backend/pipeline/create", data=new_project_data)
        print(resp.get_data(as_text=True))
        self.assertEqual(resp.status_code, 200)

    @patch('web_service.helpers.helpers._setup_couchdb')
    @patch('web_service.helpers.helpers.connect_db')            # for _get_config_from_db
    @patch('web_service.helpers.helpers.get_db_config')         # for _get_config_from_db
    @patch('web_service.database.workspace.exceeded_workspace_count_for_user')
    @patch('web_service.helpers.helpers.get_db_user_document')
    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.get_instance')
    @patch('time.sleep')                                        # to avoid sleeping for a minute
    @patch('web_service.kub.KubernetesAPI.KubernetesAPI.execute_command_in_pod')
    @patch('web_service.database.workspace.Workspace.store')
    def test_workspace_creation(self, mock_store, mock_kube_exec, mock_sleep,
                                mock_kube, mock_get_db_user_doc, mock_exceeded, mock_get_db_config,
                                mock_connect_db, mock_setup_couch_db):
        '''Test workspace creation endpoint'''
        config = {
            'user_workspace_limit': 10,
            'workspace_pod_image': 'test_pod_image',
            'service_type': 'what is this for?'
        }
        mock_get_db_config.return_value = config
        mock_exceeded.return_value = [False, []]
        mock_create_pvc_pod_return_value = [
            {'code': 201, 'resource': 'PVC', 'status': 'COMPLETED',
             'resource_name': 'test-clone-pvc',
             'message': 'PV test-clone-pv completed successfully'},
            {'code': 201, 'resource': 'Pod', 'status': 'COMPLETED',
             'resource_name': 'test-clone-pod',
             'message': 'PV test-clone-pod completed successfully'}
        ]

        def update_worskspace(workspace, merge):
            workspace['clone_name'] = 'test_clone_name'   # why _ and - ?
            workspace['pod'] = 'test_pod_name'
            workspace['source_pvc'] = 'test_source_pvc_name'
            workspace['pvc'] = 'test_pvc_name'
            workspace['pv_name'] = 'test_pv_name'
            workspace['service'] = 'test_service_name'
            workspace['pipeline_pvc'] = 'test_pvc_name'
            return mock_create_pvc_pod_return_value

        mock_kube.return_value.create_pvc_clone_and_pod.side_effect = update_worskspace

        new_workspace_data = {
            'workspace-name': 'test',
            'snapshot_name': 'test_snapshot',
            'uid': 1000,
            'gid': 1000,
            'build-name-with-status': 'testme_ok',
            'username': 'test_user',
            'pipeline-name': 'test_project',
        }
        response = self.client.post("/backend/workspace/create", data=new_workspace_data)
        self.assertEqual(response.status_code, 200)

    @patch('web_service.helpers.helpers.onetime_setup_required')
    @patch('web_service.database.workspace.purge_old_workspaces')
    def test_workspace_purge(self, mock_purge_workspace, mock_setup):
        '''Test purge workspaces endpoint'''
        mock_purge_workspace.return_value = 1, ['deleted_ws_1']
        response = self.client.post("/backend/workspace/purge")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['purged_workspaces']), 1)

    @patch('web_service.helpers.helpers._setup_couchdb')
    @patch('web_service.helpers.helpers.connect_db')            # for _get_config_from_db
    @patch('web_service.helpers.helpers.get_db_config')         # for _get_config_from_db
    @patch('web_service.database.workspace.exceeded_workspace_count_for_user')
    def test_exception_workspace_limit(self, mock_exceeded_limit, mock_get_db, mock_connect_db, mock_setup):
        '''Test exception when user exceeds workspace limit'''
        workspace_data = {
            'workspace-name': 'test',
            'build-name-with-status': 'testme_ok',
            'username': 'test_user',
            'pipeline-name': 'test_project',
        }
        mock_exceeded_limit.return_value = True, None
        response = self.client.post("/backend/workspace/create", data=workspace_data)
        self.assertEqual(response.status_code, 401)

    # TODO: To be replaced with /backend/buildclone/purge
    # @patch('web_service.helpers.helpers.get_db_config')
    # @patch('web_service.database.snapshot.Snapshot')
    # @patch('web_service.database.snapshot.purge')
    # def test_snapshot_purge(self, mock_snapshot_purge, mock_snapshot, mock_db_connect):
    #     '''Test snapshots purge endpoint'''
    #     response = self.client.post("/backend/snapshot/purge")
    #     self.assertEqual(response.status_code, 404)

    #     # TODO: To be replaced with /backend/buildclone/purge
    # @patch('web_service.helpers.helpers.get_db_config')
    # @patch('web_service.database.snapshot.Snapshot')
    # @patch('web_service.database.snapshot.purge')
    # def no_test_snapshot_purge_fail(self, mock_snapshot_purge, mock_snapshot, mock_db_connect):
    #     '''Test snapshots purge exception'''
    #     response = self.client.post("/backend/snapshot/purge", data={'type': 'invalid'})
    #     self.assertEqual(response.status_code, 404)

    #     # TODO: missing endpoint -- to be replaced with /backend/buildclone/delete
    # @patch('web_service.ontap.ontap_service.OntapService.delete_snapshot')
    # def test_snapshot_delete(self, mock_delete_snapshot):
    #     ''' Test delete snapshot endpoint '''
    #     snapshot_name = 'test_create_snapshot'
    #     mock_delete_snapshot.return_value = [
    #         {
    #             "code": 201,
    #             "error_message": "",
    #             "message": "Snapshot %s completed successfully" % snapshot_name,
    #             "resource": "Snapshot",
    #             "resource_name": snapshot_name,
    #             "status": "COMPLETED"
    #         }
    #     ]
    #     response = self.client.delete("/backend/snapshot/delete",
    #                                   data=dict(volume_name='test_volume',
    #                                             snapshot_name=snapshot_name))
    #     self.assertEqual(response.status_code, 404)
    #     # data = json.loads(response.data)[0]    # response is single JSON object enclosed in a list
    #     # self.assertEqual(data['resource_name'], snapshot_name)
