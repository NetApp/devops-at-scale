Installation
================================================================

Installing Using Helm Package Manager
--------------------------------------

1. Download source code from github

  .. code-block:: shell

    git clone https://github.com/NetApp/build-at-scale

2. Go to the "build-at-scale" directory

  .. code-block:: shell

    cd ./build-at-scale

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
	      # NSLM/API IP address
	      apiIP: ""
	      # NSLM/API username
	      user: ""
	      # NSLM/API password
	      password: ""
	      # ontap SVM/Vserver
	      svm: ""
	      # ontap aggregate
	      aggregate: ""

4. Install helm chart using following command :

  .. code-block:: shell

    	helm install --name build-at-scale build-at-scale/

  .. note:: If helm is not already installed , visit https://helm.sh/ for installation instructions
  
5. Wait for pods to reach the "Running" state:

  .. code-block:: shell

	>kubectl get pods | grep build-at-scale

	NAME                                              READY     STATUS    RESTARTS   AGE

	build-at-scale-couchdb-58f48c5b8d-vw9mb           1/1       Running   0          3m

	build-at-scale-docker-registry-7969844c9f-phshp   1/1       Running   0          3m

	build-at-scale-gitlab-6c6dc79b77-j4dww            1/1       Running   0          3m

	build-at-scale-jenkins-74d87d6fd5-th29g           1/1       Running   0          3m

	build-at-scale-webservice-5bbcdbf88c-rjrp4        1/1       Running   0          3m

  .. note:: It may take up to 10 minutes for all the pods to come up.


6. After the pods are ready, retrieve the URL for each service:

  .. code-block:: shell

  	>kubectl get svc

  			NAME                                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                                  AGE

  	build-at-scale-couchdb                     NodePort    10.108.249.65    <none>        5984:14339/TCP                           5m

  	build-at-scale-docker-registry             NodePort    10.97.110.240    <none>        5000:24646/TCP                           5m

  	build-at-scale-gitlab                      NodePort    10.102.216.157   <none>        80:*30593*/TCP,22:8639/TCP,443:18600/TCP   5m

  	build-at-scale-jenkins                     NodePort    10.99.97.28      <none>        8080:*12899*/TCP                           5m

  	build-at-scale-jenkins-agent               ClusterIP   10.100.249.190   <none>        50000/TCP                                5m

  	build-at-scale-webservice                  NodePort    10.101.38.243    <none>        5000:*12054*/TCP



  .. note:: If using the "NodePort" ServiceType, take note of the port of each service. The service will be available at <node_ip>:<service_node_port>

  .. note:: If using the "Load Balancer" ServiceType , wait for an EXTERNAL-IP to be assigned to each service

6. Using a Web Browser , open the "build-at-scale-webservice" service URL to visit the Build-At-Scale Frontend Management Console

  .. figure:: images/index.png
	  :width: 100%
	  :alt: Create CI Pipeline

  .. note:: All services can be accessed using credentials 'admin:admin' initially

Additional Configuration
--------------------------------------

**Create Intial GitLab User (Optional)**


	An initial account has to be created on Gitlab before starting to use it.
	To create an account on Gitlab, visit the following URL and sign up.

	.. code :: shell

		http://<<Kubernetes-IP>>:<<Gitlab_port>>


	.. figure:: images/gitlab.png
		:width: 100%
		:alt: GitLab
