General Usage
=================================================


Pipeline Creation
--------------------------------------
DevOps-at-Scale pipelines can be created via pipeline creation page:
  .. code:: shell

    http://<<$SERVICE_URL>>:<<devops-at-scale-webservice-port>>/frontend/pipeline/create

  .. figure:: images/create_pipeline.png
    :width: 100%
    :alt: Create CI Pipeline

  =======================       =======      ================================================================================================
  Parameter 	                  Value        Description
  =======================       =======      ================================================================================================
  SCM-URL                                    URL of the source code repository
  SCM-Branch                                 SCM branch off which the pipeline should run
  Export-policy                 default      Export-policy that should be used for the pipeline volume
  =======================       =======      ================================================================================================

Once the pipeline creation is successful, a Jenkins project with pre-populated build parameters is setup

    .. figure:: images/jenkins_pipeline_with_build_params.png
      :width: 100%
      :alt: Jenkins project for Pipeline

Integrate GitLab with Jenkins for automatic build triggers
----------------------------------------------------------------------------
1. From the webservice dashboard, copy the Jenkins URL for the pipeline created

    .. figure:: images/pipelines_table_dashboard.png
      :width: 100%
      :alt: Pipelines dashboard

2. Open GitLab from the webservice dashboard (http://<$SERVICE_URL>:<devops-at-scale-webservice-port>)

3. Login using root/root_devopsatscale

4. In the GitLab project, goto Settings -> Integrations and paste the Jenkins project URL from step (1) and create the webhook

    .. note:: When pasting the Jenkins URL, replace /job/<jenkins-project-name> with /project/<jenkins-project-name>

    .. figure:: images/create_webhook_gitlab.png
      :width: 100%
      :alt: Create Webhook Gitlab

5. In global Gitlab settings, allow outbound requests from local network

    .. figure:: images/allow_outbound_requests_gitlab.png
      :width: 100%
      :alt: Allow Outbound Requests Gitlab

6. Enable the build trigger from webhook in Jenkins.
Navigate to the pipeline's Jenkins URL from the webservice dashboard and goto Configure -> Build Triggers

    .. figure:: images/webhook_jenkins.png
      :width: 100%
      :alt: Enable build trigger Jenkins

7. Webhook setup is complete. Test the webhook setup manually from GitLab (Project -> Settings -> Integrations -> Webhook -> Test -> Push Events)

    .. figure:: images/test_webhook.png
      :width: 100%
      :alt: Test WebHook

This will validate whether the GitLab and Jenkins integration has been successful

    .. figure:: images/hook_success.png
      :width: 100%
      :alt: Successful GitLab Jenkins Integration

8. All further pushes to the GitLab project will automatically trigger a build in Jenkins project corresponding to the pipeline

    .. figure:: images/build_triggered_from_gitlab.png
      :width: 100%
      :alt: Successful build trigger on git push

Workspace Creation
--------------------------------------
DevOps-at-Scale workspaces can be created via workspace creation page:
  .. code:: shell

    http://<<$SERVICE_URL>>:<<devops-at-scale-webservice-port>>/frontend/workspace/create

  .. figure:: images/workspace.png
      :width: 100%
      :alt: TheiaIDE

  =======================       =======      ================================================================================================
  Parameter 	                  Value        Description
  =======================       =======      ================================================================================================
  Pipeline                                   Select the pipeline
  Username                                   Developer username
  Workspace prefix                           Enter a prefix which can be used to identify the workspace
  Build                                      Select the build from which the workspace should be created
  =======================       =======      ================================================================================================

  .. figure:: images/create_workspace2.png
      :width: 100%
      :alt: TheiaIDE

Once a workspace is created, you will be provided instructions on how to access your workspace via Theia Browser IDE or locally via NFS:

.. figure:: images/workspace_instructions.png
    :width: 70%
    :alt: Theia IDE

.. figure:: images/theia.png
    :width: 100%
    :alt: Theia IDE


Merge Workspace Creation
--------------------------------------
DevOps-at-Scale merge workspaces can be created via workspace creation page:
  .. code :: shell

    http://<<$SERVICE_URL>>:<<devops-at-scale-webservice-port>>/frontend/workspace/merge

Users can merge their workspace with the latest build when they feel their workspace is out of date.

This allows users to pull in the latest code and artifacts into their workspace , thus potentially providing
incrmental build time savings.

To merge workspaces, navigate to the Merge Workspace tab and fill in the following values :-

  .. figure:: images/workspacemerge.png
      :width: 100%
      :alt: Workspace Merge

  =======================       =======      ================================================================================================
  Parameter 	                  Value        Description
  =======================       =======      ================================================================================================
  Username                                   Developer username
  Workspace Name Prefix                      Enter a prefix which can be used to identify the workspace
  Source Workspace name                      Enter name of the source workspace to merge from
  Build                                      Select the build which the workspace should be created off
  =======================       =======      ================================================================================================
