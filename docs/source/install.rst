Installation
================================================================

Installing Using Helm Package Manager
--------------------------------------

1. Download source code from github

  .. code-block:: shell

    git clone https://github.com/NetApp/devops-at-scale

2. Go to the "devops-at-scale" directory

  .. code-block:: shell

    cd ./devops-at-scale

3. Enter storage details and installation options by modifying values.yaml


  .. code-block:: shell

    cat values.yaml
    global:
      # "LoadBalancer" or "NodePort"
      ServiceType: NodePort
      scm:
        # "gitlab" or "bitbucket"
        type: "gitlab"
      registry:
        # "artifactory" or "docker-registry"
        type: "artifactory"
      persistence:
        ontap:
          # If set to "true", ontap volumes for various services(E.g. gitlab/aritifactory/couchdb) will be automatically created
          automaticVolumeCreation: true
          # ontap data lif IP address
          dataIP: ""
          # ontap SVM name
          svm: ""
          # ontap aggregate
          aggregate: ""

4. Install helm chart using following command :

  .. code-block:: shell

        helm install –-name devops-at-scale .

  .. note:: If helm is not already installed , visit https://helm.sh/ for installation instructions
  
5. Wait for pods to reach the "Running" state:

  .. code-block:: shell

    >kubectl get pods | grep devops-at-scale

    NAME                                              READY     STATUS    RESTARTS   AGE

    devops-at-scale-couchdb-58f48c5b8d-vw9mb           1/1       Running   0          3m

    devops-at-scale-docker-registry-7969844c9f-phshp   1/1       Running   0          3m

    devops-at-scale-gitlab-6c6dc79b77-j4dww            1/1       Running   0          3m

    devops-at-scale-jenkins-74d87d6fd5-th29g           1/1       Running   0          3m

    devops-at-scale-webservice-5bbcdbf88c-rjrp4        1/1       Running   0          3m

  .. note:: It may take up to 10 minutes for all the pods to come up.


6. After the pods are ready, retrieve the webservice URL:

  .. code-block:: shell

    >kubectl get svc

        NAME                                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                                  AGE

    devops-at-scale-couchdb                     NodePort    10.108.249.65    <none>        5984:14339/TCP                           5m

    devops-at-scale-docker-registry             NodePort    10.97.110.240    <none>        5000:24646/TCP                           5m

    devops-at-scale-gitlab                      NodePort    10.102.216.157   <none>        80:30593/TCP,22:8639/TCP,443:18600/TCP   5m

    devops-at-scale-jenkins                     NodePort    10.99.97.28      <none>        8080:12899/TCP                           5m

    devops-at-scale-jenkins-agent               ClusterIP   10.100.249.190   <none>        50000/TCP                                5m

    devops-at-scale-webservice                  NodePort    10.101.38.243    <none>        5000:12054/TCP


    export NODE_IP=$(kubectl get nodes -o jsonpath="{.items[0].status.addresses[0].address}")
    export SERVICE_PORT=$(kubectl get -o jsonpath="{.spec.ports[0].nodePort}" services {{.Release.Name}}-webservice)
    export SERVICE_URL=$NODE_IP:$SERVICE_PORT

  .. note:: Take note of the port of web service. The web service will be available at $SERVICE_URL:<devops-at-scale-webservice-port>


7. Using a Web Browser, open the "devops-at-scale-webservice" URL (http://<$SERVICE_URL>:<devops-at-scale-webservice-port>) to visit the DevOps-At-Scale Frontend Management Console

  .. figure:: images/index.png
      :width: 100%
      :alt: Create CI Pipeline

  .. note:: GitLab service can be accessed using credentials 'root:root_devopsatscale' initially
  .. note:: All other services can be accessed using credentials 'admin:admin' initially


Additional Configuration
--------------------------------------

**Create Initial GitLab User (Optional)**


    An initial account has to be created on Gitlab before starting to use it.
    To create an account on Gitlab, visit the following URL and sign up.

    .. code :: shell

        http://<<$SERVICE_URL>>:<<Gitlab_port>>


    .. figure:: images/gitlab.png
        :width: 100%
        :alt: GitLab
