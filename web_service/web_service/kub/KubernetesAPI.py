''' Connect to Kubernetes and perform operations using Kubernetes REST API '''
from time import sleep
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream
from web_service.ontap.ontap_service import OntapService
from web_service.helpers import helpers
import os


class KubernetesAPI():
    ''' Kubernetes API methods to perform the following:
    - Create pod, PV, PVC
    - Update pod, PV, PVC '''

    def __init__(self, kub_ip=None, kub_token=None):

        try:
            config.load_incluster_config()
        except:
            # this means this web_service instance is not running within cluster
            config.load_kube_config()

        client.configuration.verify_ssl = False
        self.api = client.CoreV1Api()

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

    def create_pvc(self, vol_name, pvc_size, namespace):
        ''' Create PVC with name 'vol_name' and size 'pvc_size' '''
        body = self.create_pvc_config(vol_name, pvc_size)

        try:
            self.api.create_namespaced_persistent_volume_claim(namespace, body)
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

    def read_status(self, resource, name, namespace):
        if resource == "pv":
            return self.api.read_persistent_volume_status(name)
        elif resource == "pvc":
            return self.api.read_namespaced_persistent_volume_claim_status(name, namespace)

    def create_pv_and_pvc(self, vol_name, size, namespace, ontap_cluster_data_lif):
        ''' Create PV and PVC enabled to use the volume 'vol_name' '''
        size_to_mb = size / 1024 / 1024
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
                    "pv", pv_status['resource_name'], namespace)
                phase = status.status.phase
            pv_status['time'] = counter

        pvc_status = self.create_pvc(
            vol_name_no_underscore, size_to_mb, namespace)
        if pvc_status['code'] == 201:
            # wait for PVC to be ready!
            phase = ""
            counter = 0
            while phase != 'Bound' and counter < 10:
                counter += 1
                sleep(1)
                # removed direct call to api.pvc_status
                status = self.read_status(
                    "pvc", pvc_status['resource_name'], namespace)
                phase = status.status.phase
            pvc_status['time'] = counter

        return [pv_status, pvc_status]

    def create_pv_and_pvc_and_pod(self, workspace, size, namespace, ontap_cluster_data_lif):
        ''' Create PV, PVC and pod enabled to use volume 'vol_name' '''
        kb_clone_name = workspace['kb_clone_name']
        statuses = self.create_pv_and_pvc(
            kb_clone_name, size, namespace, ontap_cluster_data_lif)
        body = self.create_pod_config(workspace)
        service_body = self.create_service_config(workspace)

        try:
            self.api.create_namespaced_pod(namespace, body)
            self.api.create_namespaced_service(namespace, service_body)
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
                    "ReadWriteMany"
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
    def create_pod_config(workspace):
        ''' Generate dictionary to configure Pod creation '''

        volumes = [
            {
                "name": workspace['kb_clone_name'] + "-volume",
                "persistentVolumeClaim": {
                    "claimName": workspace['kb_clone_name'] + "-pvc"
                }
            },
            {
                "name": "docker-sock-volume",
                "hostPath": {
                    "path": "/var/run/docker.sock",
                    "type": ""
                }

            },
        ]
        volume_mounts = [
            {
                "mountPath": "/workspace",
                "name": workspace['kb_clone_name'] + "-volume"
            },
            {
                "mountPath": "/var/run/docker.sock",
                "name": "docker-sock-volume"
            },

        ]
        if 'source_workspace_name' in workspace:
            volumes.append({
                "name": workspace['source_workspace_name'] + "-volume",
                "persistentVolumeClaim": {
                    "claimName": workspace['source_workspace_name'] + "-pvc"
                }
            })
            volume_mounts.append({
                "mountPath": "/source_workspace",
                "name": workspace['source_workspace_name'] + "-volume"
            })

        pod_config = {
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {
                "labels": {
                    "app": workspace['kb_clone_name'] + "-pod"
                },
                "name": workspace['kb_clone_name'] + "-pod"
            },
            "spec": {
                "volumes": volumes,
                "containers": [
                    {
                        "name": workspace['kb_clone_name'] + "-container",
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
                        "command": [ "yarn", "theia", "start", "/home/project", "--hostname=0.0.0.0" ]
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
                    "app": workspace['kb_clone_name'] + "-pod"
                },
                "name": workspace['kb_clone_name'] + "-service"
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
                    "app": workspace['kb_clone_name'] + "-pod"
                },
                "type": workspace['service_type']
            }
        }

        return service_config

    def get_service_url(self, service_name, namespace="default"):
        """
        Retrieve external url for specified service
        Returns URL if found or empty string if not
        """

        try:
            # Get nodeport for service
            response = self.api.read_namespaced_service(service_name, namespace)

            # determine service service_type
            service_type=""
            if 'SERVICE_TYPE' in os.environ:
                service_type = os.environ['SERVICE_TYPE']
            if (service_type == 'LoadBalancer'):
                ip = response.status.load_balancer.ingress[0].ip
                port = response.spec.ports[0].port
            else:
                # Get worker node (anything other than master)
                ip = self.get_worker_node()
                port = response.spec.ports[0].node_port
            if not port:
                return ""
            return "%s:%s" % (str(ip), str(port))
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

    def execute_command_in_pod(self, pod_name, namespace, command):
        """
        Execute command in specified pod
        Returns output of command or empty string if there is an error
        """
        try:
            command = '/usr/bin/timeout 60 ' + command
            response = stream(self.api.connect_get_namespaced_pod_exec, pod_name, namespace,
                              command=command,
                              stderr=True, stdin=False,
                              stdout=True, tty=False)
            return response
        except ApiException as exc:
            err = "Error while running command in pod: %s\n" % (exc)
            print(err)
            return ""
    def delete_pod(self, pod_name, namespace="default"):
        """
        Delete specified pod
        """

        body = client.V1DeleteOptions()
        api_response = self.api.delete_namespaced_pod(pod_name, namespace, body)
        return api_response
