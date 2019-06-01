.. toctree::
   :maxdepth: 3
   :caption: Contents:

.. _reference:

References
================================================================

Installation and setup of Kubernetes cluster using Ansible
----------------------------------------------------------------------------
**Pre-requisites**

1. If you do not have an Ansible setup. Please setup by following the instructions `here <https://netapp.io/2018/10/08/getting-started-with-netapp-and-ansible-install-ansible/>`_

2. One or more VMs reachable from where Ansible playbooks are being run

.. note:: Ansible playbooks referred in the below steps are located in devops-at-scale/devops-at-scale/ansible-playbooks/k8s_setup

**Usage**

1. Download roles

    .. code-block:: shell

       ansible-galaxy install --roles-path roles -c geerlingguy.docker
       ansible-galaxy install --roles-path roles -c geerlingguy.kubernetes

2. Create inventory file

    .. code-block:: shell

      $ cat inventory
      [all]
      scspa0633050001 kubernetes_role="master"
      scspa0633051001 kubernetes_role="node"

If more than one node, tag them appropriately.

3. Install docker and kubernetes

    .. code-block:: shell

      ansible-playbook -i inventory -K --become-method=su --become k8s_setup_cluster.yml

This will install kudeadm, kubelet, kubectl, and create a cluster with worker nodes.


Installation and setup of Trident on Kubernetes using Ansible
----------------------------------------------------------------------------

**Pre-requisites**

1. If you do not have an Ansible setup. Please setup by following the instructions from `Ansible Setup <https://netapp.io/2018/10/08/getting-started-with-netapp-and-ansible-install-ansible/>`_

2. Kubernetes cluster. The inventory file identifies master and worker nodes.

3. ONTAP cluster

.. note:: Ansible playbooks referred in the below steps are located in devops-at-scale/devops-at-scale/ansible-playbooks/trident_setup


**Qualify your Kubernetes cluster**

    .. code-block:: shell

      ansible-playbook -i inventory kubectl_check.yml -K --become --become-method=su --extra-vars=@vsim_vars.yml
      (requires root access on K8S master node to run kubectl)

**Preparation**

1. The trident_prereqs.yml playbook will install pip, setuptool, and the openshift python package. This is required to run k8s Ansible module.

This playbook will then create a "trident" namespace.

    .. code-block:: shell

      ansible-playbook -i inventory trident_prereqs.yml -K --become --become-method=su

Download installer and final checks

2. The trident.yml playbook will install the trident installer and set up a backend storage file to support trident etcd database:

    .. code-block:: shell

      ansible-playbook -i inventory trident.yml -K --become --become-method=su --extra-vars=@vsim_vars.yml

(requires root access on K8S master node to run yum - and maybe k8s)

**Trident installation**

3. The next step will be to run the trident installer.
In the kubernetes master node:

    .. code-block::

      /root/trident/trident-installer/tridentctl install -n trident --dry-run
      /root/trident/trident-installer/tridentctl uninstall -n trident
      /root/trident/trident-installer/tridentctl install -n trident

      [root@scspa0638340001 ~]# kubectl -n trident get pods
      NAME                       READY   STATUS    RESTARTS   AGE
      trident-7df76c5dcb-q7htv   2/2     Running   0          78m

4. Check Trident is running

    .. code-block:: shell

      ansible-playbook -i inventory trident_check_pods.yml -K --become --become-method=su

As of today, you should see: 2/2 Running (1 pod is running 2 containers out of 2)

**Trident configuration**

5. The backend created in the preparation step is only used to support the Trident etcd persistent storage.
New backend(s) need to be created to support production.

**Add backend**

Being lazy here, we can reuse the same backend

    .. code-block:: shell

      trident/trident-installer/tridentctl -n trident create backend -f trident/trident-installer/setup/backend.json

6. Add storage class in Kubernetes.
Follow instructions `Trident documentation <https://netapp-trident.readthedocs.io/en/stable-v19.04/kubernetes/operations/tasks/storage-classes.html>`_

7. Test Trident installation by creating first volume and mounting it into an nginx pod.
Follow instructions `Trident example <https://netapp-trident.readthedocs.io/en/stable-v19.04/kubernetes/operations/tasks/volumes.html>`_

