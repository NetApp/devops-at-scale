.. toctree::
   :maxdepth: 3
   :caption: Contents:

.. prerequisites:

Prerequisites
=================================================
* 1 running instance of `Data ONTAP cluster <https://www.netapp.com/us/products/data-management-software/ontap.aspx>`_
* `Kubernetes cluster <https://kubernetes.io/docs/setup/>`_ RBAC cluster
* `NetApp Trident Installation with Kubernetes <https://netapp-trident.readthedocs.io/>`_
* `Helm Package manager <https://helm.sh/docs/using_helm/>`_


.. note:: Please see https://kubernetes.io/docs/setup/ for kubernetes installation instructions. Please check Trident documentation for supported Kubernetes version.

.. note:: Please ensure your Kubernetes cluster has a default storage class set up

.. note:: Please ensure your Kubernetes cluster, ONTAP cluster, and Trident can communicate with each other and reside in secure network(s)

.. note:: Please visit :ref:`reference` on how to use Ansible to automate Kubernetes cluster installation and setup

.. note:: Please visit :ref:`reference` on how to use Ansible to automate Trident installation in a Kubernetes cluster
