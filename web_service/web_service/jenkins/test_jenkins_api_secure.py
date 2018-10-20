''' Tests for jenins_api.py methods '''

import os
import sys
import unittest
from unittest.mock import patch, Mock
import web_service.jenkins.jenkins_api_secure as j

# Set project root directory so coverage.py can generate coverage
BASE_DIR = os.path.join(os.path.dirname(__file__), '../..')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class TestJenkinsAPI(unittest.TestCase):
    ''' Test Jenkins API '''
    def test_get_all_jobs(self):
        with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
            jenkins = j.JenkinsAPI(None, None, None, None)
            jenkins.jenkins_instance = Mock()
            jenkins.jenkins_instance.get_jobs.return_value = self.create_mock_jobs(['example-pipeline1', 'example-pipeline2'])
            # mock_get_jobs.return_value = self.create_mock_jobs(['example-pipeline1', 'example-pipeline2'])
            jobs = jenkins.get_all_jobs()
            self.assertTrue(len(jobs) > 1)
            expected_job_list = [job['name'] for job in jobs]
            self.assertTrue('example-pipeline2' in expected_job_list)

    # TODO: test get_last_build_status
    def test_create_job_json(self):
        '''
            Test helper to create job's JSON load
        '''
        with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
            jenkins = j.JenkinsAPI(None, None, None, None)
            jenkins.jenkins_instance = Mock()
            mock_job_list = self.create_mock_jobs(['abc123'])
            _, mock_job = mock_job_list[0]
            job_json = jenkins.create_job_json(mock_job)

            expected_job = {
                'name': mock_job.name,
                'link': mock_job.url
                }
            self.assertEqual(expected_job, job_json)

    def test_get_build_statuses(self):
        '''
            Test helper to create job's build status JSON load
        '''
        with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
            jenkins = j.JenkinsAPI(None, None, None, None)
            jenkins.jenkins_instance = Mock()
            jenkins.get_last_build_status = Mock(return_value='SUCCESS')
            mock_job_list = self.create_mock_jobs(['abc123'])
            _, mock_job = mock_job_list[0]
            job_json = jenkins.get_build_statuses(mock_job_list)

            expected_job = {
                'name': mock_job_list[0],
                'status': 'SUCCESS'
                }
            self.assertEqual([expected_job], job_json)

    def test_check_job_exists(self):
        with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
            jenkins = j.JenkinsAPI(None, None, None, None)
            jenkins.jenkins_instance = Mock()
            jenkins.jenkins_instance.jobs.__contains__ = Mock(return_value=True)
            exists = jenkins.check_job_exists('example-pipeline1')
            self.assertTrue(exists)

    def mocked_build_requests_get(*args, **kwargs):
        '''
            Mock requests.get(url, headers)
        '''
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code

            def json(self):
                return self.json_data

        if args[0] == "https://test.com/job1":
            return MockResponse({"builds": [
                {'number' : 1, 'result': 'SUCCESS'}
                ]}, 200)
        return MockResponse(None, 404)


    @patch('web_service.jenkins.jenkins_api_secure.requests.get', side_effect=mocked_build_requests_get)
    def test_get_successful_builds(self, mock_get_requests):
        '''
            Test get_successful_builds with status 'SUCCESS'
        '''
        with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
            jenkins = j.JenkinsAPI(None, None, None, None)
            jenkins.jenkins_instance = Mock()
            jenkins.check_job_exists = Mock(return_value=True)
            build_json = {
                'number': 1,
                'name': "test-build",
                'id': 123
            }
            jenkins.create_build_json = Mock(return_value=build_json)
            jenkins.get_job_url_headers = Mock(return_value=["https://test.com/job1", {}])
            jenkins.jenkins_instance.jobs.__getitem__ = Mock()

            builds = jenkins.get_successful_builds('job1')
            self.assertTrue(len(builds) == 1)

    # def test_create_trigger_purge_job(self):
    #     '''
    #         Test creation of trigger purge job in Jenkins
    #     '''
    #     with patch.object(j.JenkinsAPI, "__init__", lambda v, w, x, y, z: None):
    #         jenkins = j.JenkinsAPI(None, None, None, None)
    #         jenkins.jenkins_instance = Mock()
    #         jenkins.bx_api_key = Mock()
    #         jenkins.jenkins_instance.jobs.__getitem__ = Mock()
    #         jenkins.jenkins_instance.create_job = Mock()
    #         jenkins.check_job_exists = Mock()
    #         jenkins.check_job_exists.side_effect = [False, True]
    #
    #         job_name = "test-create-trigger-purge"
    #         params = {
    #             "type": "trigger-purge",
    #             "instance_id": "abc123",
    #             "broker_url": "abc123_broker_url",
    #             "service_username": "abc123_username",
    #             "service_password": "abc123_password"
    #         }
    #         form_fields = dict()
    #
    #         job = jenkins.create_job(job_name, params, form_fields)
    #         self.assertTrue(job)

    @staticmethod
    def create_mock_jobs(names):
        '''
            Returns mock job object
            List of tuples (job_name, <job_object>)
        '''
        jobs = list()
        for name in names:
            mock_job = Mock()
            mock_job.name = name
            mock_job.url = 'http://mock-jenkins.com/job/' + name
            mock_job_tup = (name, mock_job)
            jobs.append(mock_job_tup)
        return jobs

if __name__ == '__main__':
    unittest.main()
