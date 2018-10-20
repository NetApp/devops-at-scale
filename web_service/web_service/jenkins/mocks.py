'''
    Mock data for Jenkins API tests
'''
JOB = {
    'fullname': 'abc123',
    'url': 'http://jenkins.com/job/abc123/'
}

JOB_INFO = {
    'lastCompletedBuild' : {
        'url': 'http://jenkins.com/job/abc123/56/',
        'number': 56,
        '_class': 'org.jenkinsci.plugins.workflow.job.WorkflowRun'
    }
}

JOB_INFO_FAILURE = {
    'lastCompletedBuild' : {
        'number': 0
    }
}
