''' Connect to Jenkins instance and perfom openations using python jenkins module '''
import base64
import jenkinsapi as j
import jinja2
import logging
import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JenkinsAPI(object):
    ''' Provides API methods for the following:
    - create job
    - build job
    - get build status
    - list all jobs, builds
    '''
    def __init__(self, url, username, password):
        self.username = username
        self.password = password
        self.url = url
        self.jenkins_instance = j.jenkins.Jenkins(self.url,
                                                  self.username,
                                                  self.password,
                                                  ssl_verify=False)
    @staticmethod
    def create_job_json(job):
        '''
        Create job details in JSON format
        '''
        return {
            'name': job.name,
            'link': job.url
        }

    @staticmethod
    def create_build_json(build):
        '''
        Build data in JSON format
        '''
        return {
            'number': build._data['number'],
            'name': build._data['displayName'],
            'id': build._data['id']
        }

    def get_build_statuses(self, jobs):
        '''
        Get list of job-names with last-build-status
        '''
        job_statuses = list()
        for job in jobs:
            job_statuses.append({
                'name': job,
                'status': self.get_last_build_status(job)
            })
        return job_statuses

    def get_all_jobs(self):
        '''
        Get list of all jobs
        '''
        jobs = self.jenkins_instance.get_jobs()
        jobs_list = list()
        for _, job in jobs:
            jobs_list.append(self.create_job_json(job))
        return jobs_list

    def get_last_build_status(self, job_name):
        ''' STATUS:
        INVALID -- No builds for a given job_name
        SUCCESS -- Successfully retrieved last build status for job_name
        jenkins.NotFoundException -- Given job_name doesn't exist
        '''
        build_status = "N/A"
        try:
            job_obj = self.jenkins_instance.jobs.__getitem__(job_name)
            last_bld = job_obj.get_last_build()
        except Exception:
            return "N/A"

        # get status only if we have a valid last build
        if last_bld is not None and last_bld.get_number() != 0:
            build_status = last_bld.get_status()
        return build_status

    def get_job_url_headers(self, job_name):
        '''
        Construct url from job_name
        '''
        url = "{}/job/{}/api/json?tree=builds[number,result,displayName,id]".format(
            self.url, job_name)
        headers = {
            "Authorization": "Basic %s" % self.get_base_auth(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        return url, headers

    def get_successful_builds(self, job_name):
        ''' Get all successful builds for job_name '''
        url, headers = self.get_job_url_headers(job_name)
        successful_builds = list()
        if self.check_job_exists(job_name):
            req = requests.get(url, headers=headers, verify=False)
            dict_response = dict(req.json())
            for build in dict_response['builds']:
                if build['result'] == 'SUCCESS':
                    job_obj = self.jenkins_instance.jobs.__getitem__(job_name)
                    build_obj = job_obj.get_build(build['number'])
                    successful_builds.append(self.create_build_json(build_obj))
        return successful_builds

    def create_job(self, job_name, params, form_fields):
        ''' Create job 'job_name' '''
        if self.check_job_exists(job_name):
            logging.info("job %s already exists" % job_name)
        job_config = self.create_job_template(params, form_fields)
        self.jenkins_instance.create_job(job_name, xml=job_config)
        self.enable_job(job_name)
        return self.check_job_exists(job_name)

    @staticmethod
    def create_job_template(params, form_fields):
        ''' Create Jenkins job template, setup build parameters '''
        template_loader = jinja2.FileSystemLoader(searchpath="./web_service/templates/")
        template_env = jinja2.Environment(loader=template_loader)

        if params['type'] == 'ci-pipeline':

            template_file = "./ci_pipeline.xml"
            pipeline_volume_name = params['volume_name']

            job_template_vars = {
                "SOURCE_CODE_BRANCH" : form_fields['scm-branch'],
                "SOURCE_CODE_URL" : form_fields['scm-url'],
                "BUILDVOL" : pipeline_volume_name,
                "CONTAINER_REGISTRY": params['container_registry'],
                "GIT_VOLUME" : params['git_volume'],
                "BROKER_URL" : params['broker_url']
            }
        elif params['type'] == 'trigger-purge':
            template_file = "./purge_policy_enforcer_job.xml"
            job_template_vars = {
                "SERVICE_URL" : params['web_service_url'],
                "SERVICE_USERNAME": params['web_service_username'],
                "SERVICE_PASSWORD": params['web_service_password']
            }
        else:
            raise KeyError

        template = template_env.get_template(template_file)
        pipeline_job_config = template.render(job_template_vars)
        return pipeline_job_config

    def enable_job(self, job_name):
        '''
        Enable jenkins job
        '''
        job = self.jenkins_instance.jobs.__getitem__(job_name)
        job.enable()
        return job_name



    def delete_job(self, job_name):
        '''
        Delete jenkins job
        '''
        self.jenkins_instance.jobs.__delitem__(job_name)
        return not self.check_job_exists(job_name)

    def check_job_exists(self, job_name):
        '''
        Check if the job already exists
        '''
        return self.jenkins_instance.jobs.__contains__(job_name)

    def get_base_auth(self):
        '''
        Basic Authorization
        '''
        return base64.encodebytes(
            ('%s:%s' %(self.username, self.password)).encode()).decode().replace('\n', '')
