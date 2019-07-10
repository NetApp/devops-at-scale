''' Connect to Kubernetes and perform operations using Kubernetes REST API '''
from time import sleep
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from web_service.ontap.ontap_service import OntapService
from web_service.helpers import helpers
import os
import logging


class KubernetesAPI:
    ''' Kubernetes API methods to perform the following:
    - Create pod, PV, PVC
    - Update pod, PV, PVC '''
    # singleton class where only one instance of this class across the webservice
    # is sufficient to manage all resources/operations

    __kube_instance = None

    def __init__(self, specs):
        if KubernetesAPI.__kube_instance is not None:
            raise Exception('Only one instance of the "%s" class is allowed per deployment' % self.__class__.__name__)
        else:
            KubernetesAPI.__kube_instance = self
        # init will be called only once per deployment
        try:
            config.load_incluster_config()
        except:
            # this means this web_service instance is not running within cluster
            config.load_kube_config()

        client.configuration.verify_ssl = False
        self.api = client.CoreV1Api()
        self.namespace, self.service_type = None, None
        for key in specs:
            setattr(self, key, specs[key])

    @staticmethod
    def get_instance():
        if KubernetesAPI.__kube_instance is None:
            raise Exception('KubernetesAPI singleton instance has not been instantiated, '
                            'please initialize class and try again')
        return KubernetesAPI.__kube_instance

    @staticmethod
    def parse_exception(exc):
        ''' Extract key fields from exception
            Here we're only interesting in existing resource
        '''
        if exc.status == 409:
            if exc.reason == 'Conflict' and '"reason":"AlreadyExists"' in exc.body:
                return "AlreadyExists"
        return ""

    def create_pv(self, vol_name, pv_size, ontap_cluster_data_lif):
        ''' Create PV with name 'vol_name' and size 'pv_size' '''
        body = self.create_pv_config(
            vol_name, pv_size, ontap_cluster_data_lif)  # V1PersistentVolume

        try:
            # api_response = self.api.create_persistent_volume(body)
            self.api.create_persistent_volume(body)
            status = OntapService.set_status(
                201, "PV", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                status = OntapService.set_status(
                    200, "PV", body['metadata']['name'])
            else:
                error_message = "Exception when calling CoreV1Api->create_persistent_volume: %s\n" % exc
                status = OntapService.set_status(
                    400, "PV", body['metadata']['name'], error_message)

        return status

    def create_pvc(self, vol_name, pvc_size):
        ''' Create PVC with name 'vol_name' and size 'pvc_size' '''
        body = self.create_pvc_config(vol_name, pvc_size)

        try:
            self.api.create_namespaced_persistent_volume_claim(self.namespace, body)
            status = OntapService.set_status(
                201, "PVC", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                status = OntapService.set_status(
                    200, "PVC", body['metadata']['name'])
            else:
                err = "Exception calling CoreV1Api->create_namespaced_persistent_volume_claim: %s\n" % exc
                status = OntapService.set_status(
                    400, "PVC", body['metadata']['name'], err)

        return status

    def create_pvc_resource(self, vol_name, vol_size, storage_class):
        '''
        Create only PVC with storage class specified
        :param vol_name: name of the volume to be prefixed in PVC name
        :param vol_size: capacity of the volume in MB
        :param storage_class: Storage class to enable provisioner (Trident) to create PV and a Volume upon PVC creation
        :param namespace: Kubernetes namespace, 'default' if not specified
        :return: dict() containing status of PVC creation with details like name and associated volume
        '''
        # TODO: refactor this method, combine to more generic methods
        size_to_bytes = int(vol_size) * 1024 * 1024
        kube_pvc = self.get_kube_resource_name(vol_name, 'pvc')
        pvc_status = self.create_pvc_with_sc(kube_pvc, size_to_bytes, storage_class)
        if pvc_status['code'] == 201:
            # wait for PVC to be ready!
            phase = ""
            counter = 0
            while phase != 'Bound' and counter < 60:
                counter += 1
                sleep(1)
                # removed direct call to api.pvc_status
                status = self.read_status("pvc", pvc_status['resource_name'])
                phase = status.status.phase
            pvc_status['time'] = counter
        pvc_status['name'] = kube_pvc
        return pvc_status

    def get_kube_resource_name(self, name, resource):
        """
        Suffix the resource name with kubernetes resource type
        Choices for resource include 'pvc', 'service', 'pod'
        :param name: Name of the Kube resource
        :param resource: Type of the Kube resource
        :return: string representing the resource-name
        """
        kube_name = helpers.replace_kube_invalid_characters(name)
        return kube_name + '-' + resource

    def create_pvc_clone_resource(self, clone, source):
        '''
        Create a PVC with annotations to clone the source PVC using Trident

        :param clone: Name of the PVC being created
        :param source: Name of the PVC to clone from
        :return: status of PVC creation
        '''
        # TODO: refactor this method, combine to more generic methods
        pvc_data = self.api.read_namespaced_persistent_volume_claim(name=source, namespace=self.namespace)
        pvc_size = pvc_data.spec.resources.requests['storage']
        storage_class = pvc_data.spec.storage_class_name
        pvc_status = self.create_pvc_clone(clone, source, pvc_size, storage_class)
        if pvc_status['code'] == 201:
            # wait for PVC to be ready!
            phase = ""
            counter = 0
            while phase != 'Bound' and counter < 60:
                counter += 1
                sleep(1)
                # removed direct call to api.pvc_status
                status = self.read_status(
                    "pvc", pvc_status['resource_name'])
                phase = status.status.phase
            pvc_status['time'] = counter
        pvc_status['name'] = clone
        return pvc_status

    def create_pvc_with_sc(self, pvc_name, pvc_size, storage_class):
        ''' Create PVC with name 'vol_name' and size 'pvc_size' '''
        body = self.create_pvc_config_with_sc(pvc_name, pvc_size, storage_class)

        try:
            self.api.create_namespaced_persistent_volume_claim(self.namespace, body)
            status = OntapService.set_status(
                201, "PVC", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                status = OntapService.set_status(
                    200, "PVC", body['metadata']['name'])
            else:
                err = "Exception calling CoreV1Api->create_namespaced_persistent_volume_claim: %s\n" % exc
                status = OntapService.set_status(
                    400, "PVC", body['metadata']['name'], err)

        return status

    def create_pvc_clone(self, pvc_clone_name, pvc_source, size, storage_class):
        '''
        Create a PVC clone from a source PVC.
        For use with Trident where Trident creates an ONTAP clone and a k8s PV and maps it to the PVC
        :param pvc_clone: PVC clone name
        :param pvc_source: PVC source name to clone from
        :param size: size of the clone PVC in MB
        :param storage_class: Storage class (should match with Trident)
        :return: Status of creation
        '''
        body = self.create_pvc_clone_config(pvc_clone_name, pvc_source, size, storage_class)

        try:
            self.api.create_namespaced_persistent_volume_claim(self.namespace, body)
            status = OntapService.set_status(
                201, "PVC", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                status = OntapService.set_status(
                    200, "PVC", body['metadata']['name'])
            else:
                err = "Exception calling CoreV1Api->create_namespaced_persistent_volume_claim: %s\n" % exc
                status = OntapService.set_status(
                    400, "PVC", body['metadata']['name'], err)

        return status

    def get_pv_name_from_pvc(self, pvc_name):
        pvc_data = self.api.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=self.namespace)
        return pvc_data.spec.volume_name

    def get_volume_name_from_pvc(self, pvc_name, vol_type='nfs'):
        pv_name = self.get_pv_name_from_pvc(pvc_name)
        pv_data = self.api.read_persistent_volume(pv_name)
        volume_path = None
        if vol_type == 'nfs':
            volume_path = pv_data.spec.nfs.path
        # TODO: if volume_path is invalid, raise an exception

        return os.path.basename(volume_path)

    def read_status(self, resource, name):
        if resource == "pv":
            return self.api.read_persistent_volume_status(name)
        elif resource == "pvc":
            return self.api.read_namespaced_persistent_volume_claim_status(name, self.namespace)

    def create_pv_and_pvc(self, vol_name, size, ontap_cluster_data_lif):
        ''' Create PV and PVC enabled to use the volume 'vol_name' '''
        size_to_mb = int(size) / 1024 / 1024
        vol_name_no_underscore = helpers.replace_kube_invalid_characters(
            vol_name)
        pv_status = self.create_pv(
            vol_name_no_underscore, size_to_mb, ontap_cluster_data_lif)

        if pv_status['code'] == 201:
            # wait for PV to be ready!
            phase = ""
            counter = 0
            while phase != 'Available' and counter < 10:
                counter += 1
                sleep(1)
                status = self.read_status(
                    "pv", pv_status['resource_name'])
                phase = status.status.phase
            pv_status['time'] = counter

        pvc_status = self.create_pvc(
            vol_name_no_underscore, size_to_mb)
        if pvc_status['code'] == 201:
            # wait for PVC to be ready!
            phase = ""
            counter = 0
            while phase != 'Bound' and counter < 10:
                counter += 1
                sleep(1)
                # removed direct call to api.pvc_status
                status = self.read_status(
                    "pvc", pvc_status['resource_name'])
                phase = status.status.phase
            pvc_status['time'] = counter

        return [pv_status, pvc_status]

    def create_pv_and_pvc_and_pod(self, workspace, size, ontap_cluster_data_lif):
        ''' Create PV, PVC and pod enabled to use volume 'vol_name' '''
        kb_clone_name = workspace['kb_clone_name']
        statuses = self.create_pv_and_pvc(
            kb_clone_name, size, ontap_cluster_data_lif)
        body = self.create_pod_config(workspace)
        service_body = self.create_service_config(workspace)

        try:
            self.api.create_namespaced_pod(self.namespace, body)
            self.api.create_namespaced_service(self.namespace, service_body)
            pod_status = OntapService.set_status(
                201, "Pod", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                pod_status = OntapService.set_status(
                    200, "Pod", body['metadata']['name'])
            else:
                error_message = "Exception when calling CoreV1Api->create_namespaced_pod: %s\n" % exc
                pod_status = OntapService.set_status(
                    400, "Pod", body['metadata']['name'], error_message)

        statuses.append(pod_status)

        return statuses

    def create_pvc_clone_and_pod(self, workspace, merge=False):
        """
        Create a Kube PVC (clone), Pod and a service representing the user workspace
        Once PVC clone is created, Trident assigns an ONTAP clone and a PV
        :param workspace: workspace details dict()
        :return: status of PVC and Pod creation
        """
        logging.debug("Received workspace details:: %s" % str(workspace))
        workspace['pvc'] = self.get_kube_resource_name(workspace['name'], 'pvc')
        workspace['source_pvc'] = self.get_kube_resource_name(workspace['build_name'], 'pvc')
        workspace['pipeline_pvc'] = self.get_kube_resource_name(workspace['pipeline'], 'pvc')
        workspace['pod'] = self.get_kube_resource_name(workspace['name'], 'pod')
        workspace['service'] = self.get_kube_resource_name(workspace['name'], 'service')
        logging.debug("KUBE workspace PVC:: %s" % workspace['pvc'])
        logging.debug("KUBE workspace POD:: %s" % workspace['pod'])
        logging.debug("KUBE workspace SERVICE:: %s" % workspace['service'])
        logging.debug("KUBE workspace PIPELINE PVC:: %s" % workspace['pipeline_pvc'])
        logging.debug("KUBE workspace SOURCE (BUILD) PVC:: %s" % workspace['source_pvc'])
        clone_response = self.create_pvc_clone_resource(clone=workspace['pvc'],
                                                        source=workspace['source_pvc'])
        workspace['clone_name'] = self.get_volume_name_from_pvc(workspace['pvc'])
        workspace['pv_name'] = self.get_pv_name_from_pvc(workspace['pvc'])
        if merge:
            workspace['source_workspace_pvc'] = self.get_kube_resource_name(workspace['source_workspace_name'], 'pvc')
            workspace['source_workspace_pv'] = self.get_pv_name_from_pvc(workspace['source_workspace_pvc'])
            logging.debug("KUBE source workspace PVC:: %s" % workspace['source_workspace_pvc'])
            logging.debug("KUBE source workspace PV:: %s" % workspace['source_workspace_pv'])
        workspace['temp_pod_name'] = 'temp-pod-for-uid-gid' + workspace['name']
        temp_pod = self.create_temporary_pod_to_change_uid_gid(workspace)
        body = self.create_pod_config(workspace)
        service_body = self.create_service_config(workspace)
        logging.debug("WORKSPACE DETAILS:::: %s" % str(workspace))
        try:
            # create a temporary pod to set UID GID For workspace
            self.api.create_namespaced_pod(self.namespace, temp_pod)
            logging.info("Changing UID and GID for the workspace clone volume")
            sleep(10)   # TODO: Change this to wait on pod status
            # delete the temp pod
            self.delete_pod(workspace['temp_pod_name'])
            self.api.create_namespaced_pod(self.namespace, body)
            self.api.create_namespaced_service(self.namespace, service_body)
            # TODO: move set_status to helper?
            pod_status = OntapService.set_status(201, "Pod", body['metadata']['name'])
            service_status = OntapService.set_status(201, "Service", body['metadata']['name'])
        except ApiException as exc:
            if self.parse_exception(exc) == "AlreadyExists":
                pod_status = OntapService.set_status(200, "Pod", body['metadata']['name'])
                service_status = OntapService.set_status(200, "Service", body['metadata']['name'])
            else:
                error_message = "Exception when calling create_namespaced_pod or create_namespaced_service: %s\n" % exc
                pod_status = OntapService.set_status(400, "Pod", body['metadata']['name'], error_message)
                service_status = OntapService.set_status(400, "Service", body['metadata']['name'], error_message)

        return [clone_response, pod_status, service_status]

    @staticmethod
    def create_pv_config(vol_name, pv_size, ontap_cluster_data_lif):
        ''' Generate dictionary to configure PV creation '''
        pv_name = vol_name + "-pv"
        vol_label = vol_name + "-vol"
        junction_name = helpers.replace_ontap_invalid_char(vol_name)

        pv_config = {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {
                "name": pv_name,
                "labels": {
                    "netapp-use": vol_label
                }
            },
            "spec": {
                "capacity": {
                    "storage": "%sM" % pv_size
                },
                "accessModes": [
                    "ReadWriteMany"
                ],
                "nfs": {
                    "server": ontap_cluster_data_lif,
                    "path": "/" + junction_name
                }
            }
        }

        return pv_config

    @staticmethod
    def create_pvc_config(vol_name, pv_size):
        ''' Generate dictionary to configure PVC creation '''
        pvc_name = vol_name + "-pvc"
        vol_label = vol_name + "-vol"

        pvc_config = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": pvc_name,
                "annotations": {
                    "volume.beta.kubernetes.io/storage-class": ""
                }
            },
            "spec": {
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "resources": {
                    "requests": {
                        "storage": pv_size
                    }
                },
                "selector": {
                    "matchLabels": {
                        "netapp-use": vol_label
                    }
                }
            }
        }

        return pvc_config

    @staticmethod
    def create_pvc_config_with_sc(pvc_name, pv_size, storage_class):
        ''' Generate dictionary to configure PVC creation '''
        pvc_config = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": pvc_name,
            },
            "spec": {
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "resources": {
                    "requests": {
                        "storage": pv_size
                    }
                },
                # "storageClassName": storage_class,
                # "selector": {
                #     "matchLabels": {
                #         "netapp-use": vol_label
                #     }
                # }
            }
        }
        # Set Storage class only if specified
        if storage_class is not None:
            pvc_config['spec']['storageClassName'] = storage_class
        return pvc_config

    @staticmethod
    def create_pvc_clone_config(pvc_clone_name, pvc_source, pvc_size, storage_class):
        ''' Generate PVC clone configuration '''
        pvc_config = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": pvc_clone_name,
                "annotations": {
                    "trident.netapp.io/cloneFromPVC": pvc_source
                }
            },
            "spec": {
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "resources": {
                    "requests": {
                        "storage": pvc_size
                    }
                },
                "storageClassName": storage_class,
            }
        }

        return pvc_config

    # TODO: Refactor: Merge this and below create_pod_config to one method
    def create_temporary_pod_to_change_uid_gid(self, workspace):
        volumes = [
            {
                "name": workspace['pv_name'],
                "persistentVolumeClaim": {
                    "claimName": workspace['pvc']
                }
            },
        ]
        volume_mounts = [
            {
                "mountPath": "/workspace",
                "name": workspace['pv_name']
            },
        ]
        uid_gid = str(workspace['uid']) + ":" + str(workspace['gid'])
        pod_config = {
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {
                "name": workspace['temp_pod_name']
            },
            "spec": {
                "volumes": volumes,
                "containers": [
                    {
                        "name": workspace['name'] + "-container",
                        "image": workspace['pod_image'],
                        "ports": [
                            {
                                "containerPort": 6000,
                                "name": 'debug',
                            }
                        ],
                        "volumeMounts": volume_mounts,
                        "imagePullPolicy": 'Always',
                    }
                ],
                "initContainers": [
                    {
                        # Having a security context with RunAsUser and fsGroup does not work for NFS mounts.
                        # Use init containers to map UID GID w.r.t workspace ownership
                        "command": [
                            # for merge, though we have two workspace mounts, we need uid/gid on the primary workspace
                            "chown", "-R", uid_gid, "/workspace"
                        ],
                        "name": "volume-mount-hack-for-uid-gid-mapping",
                        "image": "busybox",
                        "volumeMounts": volume_mounts
                    }
                ],
            }
        }
        return pod_config

    def create_pod_config(self, workspace):
        ''' Generate dictionary to configure Pod creation '''

        volumes = [
            {
                "name": workspace['pv_name'],
                "persistentVolumeClaim": {
                    "claimName": workspace['pvc']
                }
            },
        ]
        volume_mounts = [
            {
                "mountPath": "/workspace",
                "name": workspace['pv_name']
            },
        ]
        if 'source_workspace_name' in workspace:
            volumes.append({
                "name": workspace['source_workspace_pv'],
                "persistentVolumeClaim": {
                    "claimName": workspace['source_workspace_pvc']
                }
            })
            volume_mounts.append({
                "mountPath": "/source_workspace",
                "name": workspace['source_workspace_pv']
            })
        pod_config = {
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {
                "labels": {
                    "app": workspace['pod']
                },
                "name": workspace['pod']
            },
            "spec": {
                # Run pod with developer UID and GID.
                "securityContext": {
                    "runAsUser": workspace['uid'],
                    "runAsGroup": workspace['gid'],
                },
                "volumes": volumes,
                "containers": [
                    {
                        "name": workspace['name'] + "-container",
                        "image": workspace['pod_image'],
                        "ports": [
                            {
                                "containerPort": 3000,
                                "name": 'ide',
                            },
                            {
                                "containerPort": 6000,
                                "name": 'debug',
                            }
                        ],
                        "volumeMounts": volume_mounts,
                        "imagePullPolicy": 'Always',
                        "command": ["yarn", "theia", "start", "/home/project", "--hostname=0.0.0.0"]
                    }
                ],
            }
        }
        return pod_config

    @staticmethod
    def create_service_config(workspace):
        ''' Generate dictionary for service creation '''
        service_config = {
            "kind": "Service",
            "apiVersion": "v1",
            "metadata": {
                "labels": {
                    "app": workspace['pod']
                },
                "name": workspace['service']
            },
            "spec": {
                "ports": [
                    {
                        "name": "ide",
                        "port": 3000,
                        "protocol": "TCP"
                    },
                    {
                        "name": "debug",
                        "port": 6000,
                                "protocol": "TCP"
                    }
                ],
                "selector": {
                    "app": workspace['pod']
                },
                "type": workspace['service_type']
            }
        }

        return service_config

    def get_service_type(self, service_name):
        try:
            response = self.api.read_namespaced_service(name=service_name, namespace=self.namespace)
            # determine service service_type
            return response.spec.type
        except ApiException as exc:
            err = "Error while retrieving service type for %s: %s\n" % (service_name, exc)
            print(err)

    def get_service_url(self, service_name):
        """
        Retrieve external url for specified service
        Returns URL if found or empty string if not
        """
        try:
            # Get nodeport for service
            response = self.api.read_namespaced_service(name=service_name, namespace=self.namespace)
            # determine service service_type
            if self.service_type == 'LoadBalancer':
                ip = response.status.load_balancer.ingress[0].ip
                port = response.spec.ports[0].port
            else:
                # Get worker node (anything other than master)
                ip = self.get_worker_node()
                port = response.spec.ports[0].node_port
            if not port:
                return ""
            return "http://%s:%s" % (str(ip), str(port))
        except ApiException as exc:
            err = "Error while retrieving service url for %s: %s\n" % (
                service_name, exc)
            print(err)
        return ""

    def get_worker_node(self):
        """
        Retrieve any worker node
        Returns node hostname if found or empty string if not
        """

        try:
            for address in self.api.list_node().items[0].status.addresses:
                if address.type == 'InternalIP':
                    return str(address.address)
                pass
        except ApiException as exc:
            err = "Error while retrieving worker node: %s\n" % (exc)
            print(err)
        return ""

    def execute_command_in_pod(self, pod_name, command):
        """
        Execute command in specified pod
        Returns output of command or empty string if there is an error
        """
        try:
            command = '/usr/bin/timeout 60 ' + command
            logging.info("RUNNING COMMAND:: " + command)
            response = stream(self.api.connect_get_namespaced_pod_exec, pod_name, namespace=self.namespace,
                              command=command,
                              stderr=True, stdin=False,
                              stdout=True, tty=False)
            logging.info("RESPONSE FROM POD:: " + response)
            return response
        except ApiException as exc:
            err = "Error while running command in pod: %s\n" % (exc)
            print(err)
            return ""

    def delete_pod(self, pod_name):
        """
        Delete specified pod
        """

        body = client.V1DeleteOptions()
        api_response = self.api.delete_namespaced_pod(name=pod_name, namespace=self.namespace, body=body)
        return api_response

    def delete_pvc(self, pvc_name):
        """
        Delete specified PVC
        If using Trident, Trident deletes the associated PV and ONTAP volume/clone
        """
        body = client.V1DeleteOptions()
        api_response = self.api.delete_namespaced_persistent_volume_claim(name=pvc_name, namespace=self.namespace, body=body)
        return api_response

    def delete_service(self, service_name):
        """
        Delete specified Service
        """
        api_response = self.api.delete_namespaced_service(name=service_name, namespace=self.namespace)
        return api_response
