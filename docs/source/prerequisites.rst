.. toctree::
   :maxdepth: 3
   :caption: Contents:

.. prerequisites:

Prerequisites
=================================================
* 1 running instance of `Data Ontap <https://www.netapp.com/us/products/data-management-software/ontap.aspx>`_
* 1 running instance of `NetApp Service Level Manager(NSLM) <https://mysupport.netapp.com/documentation/docweb/index.html?productID=62414&language=en-US>`_
* Kubernetes 1.9+ RBAC cluster


.. note:: Please see https://kubernetes.io/docs/setup/ for kubernetes installation instructions

.. note:: Please ensure your kubernetes cluster, ontap cluster , and NSLM instance can communicate with each other and reside in secure network(s)

.. note::
		  Please take note of the following ontap storage configuration details, this information will be needed later:
				#. Data LIF IP:                        ________________________
				#. Storage virtual machine(SVM) name:  ________________________
				#. NSLM server IP:                     ________________________
				#. NSLM username:                      ________________________
				#. NSLM password:                      ________________________
				#. Aggregate name:                     ________________________

.. note:: ontap volumes must have an "anon" value of 0. This is needed so that various kubernetes services can write to the same volume without permission issues
