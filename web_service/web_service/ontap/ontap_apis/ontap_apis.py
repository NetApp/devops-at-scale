"""
NetApp-Jenkins Integration Scripts
      This script was developed by NetApp to help demonstrate NetApp
          technologies.  This script is not officially supported as a
          standard NetApp product.

 Purpose: Script to create a new build artifact archival volume/Local repo Volume.


 Usage:   %> Volume_create.py <args>

 Author:  Vishal Kumar S A (vishal.kumarsa@netapp.com)
          Akshay Patil (akshay.patil@netapp.com)
          Laurent/Alex (laurentn@netapp.com)

 NETAPP CONFIDENTIAL
 -------------------
 Copyright 2016 NetApp, Inc. All Rights Reserved.

 NOTICE: All information contained herein is, and remains the property
 of NetApp, Inc.  The intellectual and technical concepts contained
 herein are proprietary to NetApp, Inc. and its suppliers, if applicable,
 and may be covered by U.S. and Foreign Patents, patents in process, and are
 protected by trade secret or copyright law. Dissemination of this
 information or reproduction of this material is strictly forbidden unless
 permission is obtained from NetApp, Inc.
"""
import base64
import logging
import requests
import time
from datetime import datetime
import argparse
import sys
import re

# urllib3 is imported dynamically, pylint has no visibility
requests.packages.urllib3.disable_warnings()    # pylint: disable=no-member

# time for a job to complete ?
TIMEOUT = 60

# utility functions


def get_size(vol_size):
    """ convert size from megabyte to kilobytes """
    tmp = int(vol_size) * 1024 * 1024
    return tmp


def check_http_response(response, expected_status_code):
    """ validate http status code """
    status = response.status_code
    if status == expected_status_code:
        return True
    if status == 401:   # unauthorized
        msg = "ERROR: status = %s - Invalid credentials?" % status
        raise requests.ConnectionError(msg)
    if status in [404, 500]:   # unknown resource, operation cannot be performed
        """ response 404 cannot be jsonified """
        error = "Operation cannot be performed, retry with valid parameters"
        raise IOError(error)
    return False


def check_job_status(response):
    """ retrieve details for job status and error message """
    error_message = ""
    status_code = response["status"]["code"]
    if status_code == "SUCCESS":
        results = response["result"]
        records = results["records"]
        if len(records) == 1:
            request_status = records[0]['status']
            if request_status == "FAILED":
                error_message = records[0]['error_message']
        else:
            request_status = "ERROR: got %s record(s)" % len(records)
    else:
        request_status = "ERROR: status_code = %s" % status_code
    return request_status, error_message


class Aggregate(object):
    """ ONTAP aggregate to support volume creation """

    def __init__(self, svm_name, aggregate_name, api_server):
        """ aggregate object mirrors an existing ONTAP aggregate """
        self.aggr_name = aggregate_name
        self.svm_name = svm_name
        self.api_server = api_server

    def get_key_aggr(self):
        """ get uuid for an aggregate """
        tmp = dict(self.api_server.get_aggrs())
        aggrs = tmp['result']['records']
        for i in aggrs:
            if i['name'] == self.aggr_name:
                return i['key']

    def get_volume(self, vol_name):
        """ get specified volume in aggregate """

        url = self.api_server.get_url("ontap/aggregates/{}/volumes?name={}".format(self.get_key_aggr(), vol_name))
        headers = self.api_server.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_volumes(self):
        """ get all volumes for aggregate """
        url = self.api_server.get_url("ontap/aggregates/{}/volumes/".format(self.get_key_aggr()))
        headers = self.api_server.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def check_vol_junction(self, vol_name, junction_name):
        """ verify junction exists for a volume """
        tmp = dict(self.get_volume(vol_name))
        vols = tmp['result']['records']
        for vol in vols:
            if vol['name'] == vol_name and vol['junction_path'] == junction_name:
                return True
        return False


class Volume(object):
    """ ONTAP volume to support snapshots and clones """

    def __init__(self, volume_name, aggregate):
        """ TODO should we create the volume? """
        if aggregate is None:
            raise KeyError("Undefined aggregate for volume: %s" % volume_name)
        self.volume_name = volume_name
        self.aggregate = aggregate

    def get_key_vol(self):
        """ get uuid for a volume """
        tmp = dict(self.aggregate.get_volume(self.volume_name))
        vols = tmp['result']['records']
        for i in vols:
            if i['name'] == self.volume_name:
                return i['key']

    def check_vol(self):
        """ verify volume exists """
        tmp = dict(self.aggregate.get_volume(self.volume_name))
        vols = tmp['result']['records']
        names = [i['name'] for i in vols]
        return self.volume_name in names

    def get_size(self):
        """ get volume size """
        tmp = dict(self.aggregate.get_volume(self.volume_name))
        vols = tmp['result']['records']
        for i in vols:
            if i['name'] == self.volume_name:
                return i['size_total']
        raise KeyError(self.volume_name)

    def get_size_used(self):
        """ get volume size used """
        tmp = dict(self.aggregate.get_volume(self.volume_name))
        vols = tmp['result']['records']
        for i in vols:
            if i['name'] == self.volume_name:
                return i['size_used']
        raise KeyError(self.volume_name)

    def get_uid_gid(self):
        """ get uid and gid for a volume """
        tmp = dict(self.aggregate.get_volume(self.volume_name))
        vols = tmp['result']['records']
        for i in vols:
            if i['name'] == self.volume_name:
                return {
                    'uid': i['security_user_id'],
                    'gid': i['security_group_id']
                }
        raise KeyError(self.volume_name)

    def get_volume_atime(self):
        """get atime - access timestamp from volume"""
        vol_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}".format(vol_key))
        headers = self.aggregate.api_server.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            response_dict = response.json()
            return {
                # TODO: Fill in with the appropriate atime timestamp attribute/api
                # 'atime': response_dict['result']['records'][0]['atime'],
                # TODO: Remove hard-coded timestamp and replace with appropriate value
                'atime': datetime.now().timestamp()
            }
        return {}

    def get_snapshots(self):
        """ get list of all snapshots for one volume """
        volume_key = self.get_key_vol()
        if volume_key is None:
            error_message = "Unexistent volume name: %s" % self.volume_name
            return [], error_message

        url = self.aggregate.api_server.get_url("ontap/snapshots?volume_key={}".format(volume_key))
        headers = self.aggregate.api_server.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json(), ""
        return [], "Error 111"

    def get_all_weekly_snapshots(self):
        """
        Get all weekly snapshots for this volume or clone
        Returns list(weekly.snapshots)
        """
        data, error_message = self.get_snapshots()
        if not data:
            return None, error_message
        tmp = dict(data)
        snapshots = tmp['result']['records']
        weekly_snapshots = list()
        for snap in snapshots:
            # if this is a weekly snapshot
            if "weekly." in snap['name']:
                weekly_snapshots.append(snap)
        return weekly_snapshots

    def get_all_hourly_snapshots(self):
        """
        Get all hourly snapshots for this volume or clone
        Returns list(hourly.snapshots)
        """
        data, error_message = self.get_snapshots()
        if not data:
            return None, error_message
        tmp = dict(data)
        snapshots = tmp['result']['records']
        hourly_snapshots = list()
        for snap in snapshots:
            # if this is a weekly snapshot
            if "hourly." in snap['name']:
                hourly_snapshots.append(snap)
        return hourly_snapshots

    def get_snapdiff(self, base, previous):
        """
            get list of file differences between base and previous snapshot
            returns number of file differences
        """
        volume_key = self.get_key_vol()
        if volume_key is None:
            error_message = "Unexistent volume name: %s" % self.volume_name
            return [], error_message
        base_snapshot_key, error_message = self.get_key_snapshot(base)
        previous_snapshot_key, error_message = self.get_key_snapshot(previous)
        url = self.aggregate.api_server.get_url("ontap/snapshots/{}/files?base_snapshot_key={}".format(
            base_snapshot_key, previous_snapshot_key))
        headers = self.aggregate.api_server.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            tmp = dict(response.json())
            return tmp["result"]["total_records"]
        # TODO: handle error

    def get_clones(self):
        """ get all clones associated with this volume """
        url = self.aggregate.api_server.get_url(
            "ontap/volumes?clone_parent_key={}".format(self.get_key_vol()))
        headers = self.aggregate.api_server.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_key_snapshot(self, snapshot_name):
        """ get uuid for a snapshot """
        data, error_message = self.get_snapshots()
        if not data:
            return None, error_message
        tmp = dict(data)
        snaps = tmp['result']['records']
        for i in snaps:
            if i['name'] == snapshot_name:
                return i['key'], ""
        return None, ("cannot find snapshot: %s", snapshot_name)

    def check_snapshot(self, snapshot_name):
        """ verify a snapshot exists for a volume """
        data, _ = self.get_snapshots()
        if not data:
            return False
        tmp = dict(data)
        snapshots = tmp['result']['records']
        names = [snap['name'] for snap in snapshots]
        return snapshot_name in names

    def get_jpath(self):
        """ extract junction path from a json list of volumes for one volume """
        tmp = dict(self.aggregate.get_volumes())
        vols = tmp['result']['records']
        for vol in vols:
            if vol['name'] == self.volume_name:
                return vol['junction_path']

    def make_volume(self, vol_size, uid, gid, export_policy="default"):
        """
            create a volume for an aggregate and svm
            volume size is in megabyte
         """
        url = self.aggregate.api_server.get_url("ontap/volumes/")

        headers = self.aggregate.api_server.get_headers()
        data = {
            "aggregate_key": self.aggregate.get_key_aggr(),
            "size": get_size(vol_size),
            "storage_vm_key": self.aggregate.api_server.get_key_svm(self.aggregate.svm_name),
            "name": self.volume_name,
            "security_user_id": uid,
            "security_group_id": gid,
            "junction_path": '/' + self.volume_name,
            "security_permissions": "777",
            "security_style": "unix",
            "is_snap_dir_access_enabled": "False",
            "export_policy_key": self.aggregate.api_server.get_key_export_policy(export_policy)
        }
        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message

    def make_snapshot(self, snapshot_name):
        """ create a snapshot for a volume """

        url = self.aggregate.api_server.get_url("ontap/snapshots/")

        headers = self.aggregate.api_server.get_headers()
        data = {
            "volume_key": self.get_key_vol(),
            "name": snapshot_name,
        }
        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            snapshot = Volume(snapshot_name, self.aggregate)
            return self.aggregate.api_server.get_job_status(job_url) + (snapshot,)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, None

    def make_clone(self, snapshot_name, clone_name, uid, gid):
        """ create a clone from a snapshot """
        volume_key = self.get_key_vol()
        snapshot_key, error_message = self.get_key_snapshot(snapshot_name)
        if snapshot_key is None:
            return "ERROR: cannot get snapshot key", error_message, None
        users = {'uid': uid, 'gid': gid} if (uid != "" and gid != "") else self.get_uid_gid()

        url = self.aggregate.api_server.get_url("ontap/volumes/{}/jobs/clone".format(volume_key))

        headers = self.aggregate.api_server.get_headers()
        data = {
            "volume_clone_name": clone_name,
            "snapshot_key": snapshot_key,
            "security_user_id": users['uid'],
            "security_group_id": users['gid']
        }

        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            clone = Volume(clone_name, self.aggregate)
            return self.aggregate.api_server.get_job_status(job_url) + (clone,)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, None

    def make_clone_without_snapshot(self, clone_name, uid, gid):
        """ ONTAP will automatically create a snapshot to support the clone """
        volume_key = self.get_key_vol()
        users = {'uid': uid, 'gid': gid} if (uid != "" and gid != "") else self.get_uid_gid()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}/jobs/clone".format(volume_key))
        headers = self.aggregate.api_server.get_headers()
        data = {
            "volume_clone_name": clone_name,
            "security_user_id": users['uid'],
            "security_group_id": users['gid']
        }

        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            clone = Volume(clone_name, self.aggregate)
            return self.aggregate.api_server.get_job_status(job_url) + (clone,)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, None

    def mount(self):
        """ create a junction path for a clone """
        volume_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}/jobs/mount".format(volume_key))
        headers = self.aggregate.api_server.get_headers()
        junction_name = "/" + self.volume_name
        data = {
            "junction_path": junction_name
        }

        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url) + (junction_name,)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, ""

    def unmount(self):
        """ unmount volume or clone """
        volume_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}/jobs/unmount".format(volume_key))
        headers = self.aggregate.api_server.get_headers()
        data = {
            "force": True
        }
        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message

    def online_volume(self):
        """ try to move a volume to online state """
        volume_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}".format(volume_key))
        headers = self.aggregate.api_server.get_headers()
        data = {
            "state": "online"
        }
        response = requests.put(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, ""

    def offline_volume(self):
        """ try to move a volume to offline state """
        volume_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}".format(volume_key))
        headers = self.aggregate.api_server.get_headers()
        data = {
            "state": "offline"
        }
        response = requests.put(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message, ""

    def delete_volume(self):
        """ try to delete a volume """
        volume_key = self.get_key_vol()
        url = self.aggregate.api_server.get_url("ontap/volumes/{}".format(volume_key))
        headers = self.aggregate.api_server.get_headers()

        response = requests.delete(url, headers=headers, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message

    def unmount_offline_delete_volume(self):
        """ delete a volume (or clone) by unmounting and offlining first """
        status, error_message = self.unmount()
        if status != "COMPLETED":
            return status, "ERROR: unmounting %s" % self.volume_name, error_message
        status, error_message = self.offline_volume()
        if status != "COMPLETED":
            return status, "ERROR: offlining %s" % self.volume_name, error_message
        status, error_message = self.delete_volume()
        if status != "COMPLETED":
            return status, "ERROR: deleting %s" % self.volume_name, error_message
        return status, "", ""

    def delete_clone(self, clone_name):
        """ try to delete a clone for a volume """
        clone_to_delete = Volume(clone_name, self.aggregate)
        status, error_message, error_message2 = \
            clone_to_delete.unmount_offline_delete_volume()
        return status, error_message, error_message2

    def delete_all_clones(self):
        """ try to delete all clones for a volume """
        deleted_clones = list()
        undeleted_clones = list()
        clones = self.get_clones()
        if clones:
            clone_names = [i['name'] for i in clones['result']['records']]
            for clone_name in clone_names:
                status, error_message, error_message2 = self.delete_clone(clone_name)
                if status != "COMPLETED":
                    logging.error("Failed to Delete all clones: Status: %s, Error: %s, Error 2: %s", status,
                                  error_message, error_message2)
                    undeleted_clones.append(clone_name)
                else:
                    deleted_clones.append(clone_name)
        return deleted_clones, undeleted_clones

    def delete_snapshot(self, snapshot_name):
        """ try to delete a volume """
        snapshot_key, error_message = self.get_key_snapshot(snapshot_name)
        if snapshot_key is None:
            return "ERROR: cannot get snapshot key", error_message
        url = self.aggregate.api_server.get_url("ontap/snapshots/{}".format(snapshot_key))
        headers = self.aggregate.api_server.get_headers()

        response = requests.delete(url, headers=headers, verify=False)
        if check_http_response(response, 202):
            job_url = response.headers['Location']
            return self.aggregate.api_server.get_job_status(job_url)
        error_message = str(response.json()['status']['error']['reason']) or ""
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message

    def get_all_storage_service_levels(self):
        url = self.aggregate.api_server.get_url("slo/storage-service-levels/", version="1.0")
        headers = self.aggregate.api_server.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_ssl_key(self, ssl_name):
        result = self.get_all_storage_service_levels()
        service_levels = result['result']['records']
        for ssl in service_levels:
            if ssl['name'].lower() == ssl_name:
                return ssl['key']

    def get_all_file_shares(self):
        url = self.aggregate.api_server.get_url("slo/file-shares/", version="1.0")
        headers = self.aggregate.api_server.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_key_file_share(self, resource_name):
        result = self.get_all_file_shares()
        resources = result['result']['records']
        for resource in resources:
            if resource['name'].lower() == resource_name:
                return resource['key']

    def modify_ssl(self, ssl_name):
        """ apply ssl to volume """
        resource_key = self.get_key_file_share(self.volume_name)
        ssl_key = self.get_ssl_key(ssl_name)
        url = self.aggregate.api_server.get_url("slo/file-shares/{}".format(resource_key), version="1.0")
        data = {
            "storage_service_level_key": ssl_key
        }
        headers = self.aggregate.api_server.get_headers()
        response = requests.put(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []


class APIServer(object):
    """ python wrappers around ONTAP API services (NSLM) """

    def __init__(self, api, apiuser, apipass, debug=False):
        """ collect global values for API authentication """
        self.api = api
        self.apiuser = apiuser
        self.apipass = apipass
        self.debug = debug
        self.base_url = "https://{}/api".format(self.api)

    def get_base_auth(self):
        """ get base authentication from credentials """
        # for compatibility with python2.7
        return base64.encodestring(('%s:%s' % (self.apiuser, self.apipass))  # pylint: disable=deprecated-method
                                   .encode()).decode().replace('\n', '')

    def get_url(self, url, version="2.0"):  # use version = "5.0" if using with APIServices 2.0.
        """ build url using common prefix """
        return "{}/{}/{}".format(self.base_url, version, url)

    def get_headers(self):
        """ http header for get and post request """
        headers = {
            "Authorization": "Basic %s" % self.get_base_auth(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        return headers

    def get_aggrs(self):
        """ get list of all aggregates """
        url = self.get_url("ontap/aggregates")
        headers = self.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_svms(self):
        """ get list of all svms aka Storage-VMs """
        url = self.get_url("ontap/storage-vms/")
        headers = self.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_export_policies(self):
        """ get list of all export policies"""
        url = self.get_url("ontap/export-policies/")
        headers = self.get_headers()
        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_svm_aggregate_relationships(self):
        """ get list of all svms/aggregate relationships """
        url = self.get_url("ontap/storage-vm-aggregate-relationships/")
        headers = self.get_headers()

        response = requests.get(url, headers=headers, verify=False)
        if check_http_response(response, 200):
            return response.json()
        return []

    def get_key_svm(self, svm_name):
        """ get uuid for a svm """
        tmp = dict(self.get_svms())
        svms = tmp['result']['records']
        for i in svms:
            if i['name'] == svm_name:
                return i['key']

    def get_key_export_policy(self, export_policy_name):
        """ get uuid for a export policy """
        tmp = dict(self.get_export_policies())
        policies = tmp['result']['records']
        for i in policies:
            if i['name'] == export_policy_name:
                return i['key']

    def get_job_status(self, url):
        """ verify job status and wait for job to complete """
        error_message = ""
        headers = self.get_headers()
        retry = TIMEOUT
        while retry > 0:
            response = requests.get(url, headers=headers, verify=False)
            if check_http_response(response, 200):
                request_status, error_message = check_job_status(response.json())
                if request_status != "STARTED":
                    break
                retry -= 1
                time.sleep(1)
            else:
                request_status = "ERROR: HTTP status_code = %s" % response.status_code
        else:
            logging.error("timeout, waiting %s seconds for job to complete", TIMEOUT)
        return request_status, error_message

    def attach_cluster(self, ip_address, ontap_username, ontap_password):
        """ attach NSLM to an ONTAP cluster (a storage system) """
        url = self.get_url("admin/storage-systems/", "1.0")
        headers = self.get_headers()
        data = [
            {
                "name": ip_address,
                "hostname": ip_address,
                "type": {
                    "type": "Ontap"
                },
                "connections": [
                    {
                        "access_protocol": "ONTAP_API",
                        "access_parameters": [
                            {
                                "name": "Username",
                                "value": ontap_username
                            },
                            {
                                "name": "Password",
                                "value": ontap_password
                            },
                            {
                                "name": "Port",
                                "value": "443"
                            }
                        ]
                    }
                ]
            }
        ]
        response = requests.post(url, headers=headers, json=data, verify=False)
        if check_http_response(response, 202):
            return "COMPLETED", ""
        if check_http_response(response, 400) and response.json()['status']['error']['errno'] == 2004:
            logging.info("ONTAP cluster already attached: %s", response.json()['status']['error']['reason'])
            return "COMPLETED", "ONTAP cluster already attached"
        error_message = str(response.json()['status']['error']['reason']) or ""
        logging.error("attach_cluster failed with %s, reason: %s", response.status_code, error_message)
        return "ERROR: HTTP status_code = %s" % response.status_code, error_message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-api", help="API server IP", required=True)
    parser.add_argument("-apiuser", help="API user", required=True)
    parser.add_argument("-apipass", help="API user password", required=True)
    parser.add_argument("-svm_name", help="SVM name", required=True)
    parser.add_argument("-aggr_name", help="aggregate name", required=True)
    parser.add_argument('-create-volume', help="create a volume", action="store_true", default=False)
    parser.add_argument("-vol_names", help="comma separated list of volume names")
    parser.add_argument("-vol_size", help="volume size")
    parser.add_argument("-uid", help="uid")
    parser.add_argument("-gid", help="gid")
    parser.add_argument("-export_policy", help="export policy")
    args = parser.parse_args()

    if args.create_volume:
        if not args.vol_names:
            print("No volumes specified!")
            sys.exit(-1)
        for vol in args.vol_names.split(','):
            api_server = APIServer(args.api, args.apiuser, args.apipass)
            aggregate = Aggregate(args.svm_name, args.aggr_name, api_server)
            volume = Volume(vol, aggregate)
            # Determine volume size
            match_size = re.match(r'^(\d*)\s?([m|M][i|I]?[B|b]?)?$', args.vol_size)
            size = match_size.group(1)
            status, error_message = volume.make_volume(size, args.uid, args.gid, args.export_policy)
            if status != 'COMPLETED':
                print(error_message)
                print("Error creating volume %s" % vol)
                sys.exit(-1)
            print("volume %s created succesfully" % vol)
    sys.exit(0)


if __name__ == "__main__":
    main()
