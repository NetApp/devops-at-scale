'''
Ontap Service to act as interfact between Service server and Ontap API,
located at prohibition_service/ontap_apis/ontap_apis.py.
'''
import logging
import os
from datetime import datetime
import yaml
from web_service.ontap.ontap_apis.ontap_apis import Aggregate, APIServer, Volume

# BASEDIR = os.path.dirname(os.path.realpath(__file__))
# sys.path.insert(0, os.path.dirname(BASEDIR))
# del BASEDIR
#pylint: disable=wrong-import-position

class OntapService(object):
    '''ontap service class'''
    def __init__(self, api, apiuser, apipass, svm_name, aggr_name, data_ip):
        self.api = api
        self.apiuser = apiuser
        self.apipass = apipass
        self.svm_name = svm_name
        self.aggr_name = aggr_name
        self.data_ip = data_ip
        self.api_server = APIServer(api, apiuser, apipass)
        self.aggregate = Aggregate(svm_name,aggr_name, self.api_server)

    def attach_cluster(self, ip_address, ontap_username, ontap_password):
        return self.api_server.attach_cluster(ip_address, ontap_username, ontap_password)

    def create_volume(self, vol_name, vol_size, uid, gid, export_policy='default'):
        '''Create ONTAP volume'''
        volume = Volume(vol_name, self.aggregate)

        status, error_message = volume.make_volume(vol_size, uid, gid, export_policy)

        if status != "COMPLETED":
            if error_message == "Duplicate volume name %s.  (errno=17)" % vol_name:
                vol_status = self.set_status(200, "Volume", vol_name)
            else:
                vol_status = self.set_status(400, "Volume", vol_name, error_message)
        else:
            vol_status = self.set_status(201, "Volume", vol_name)

        vol_size = ""
        if vol_status['code'] != 400:
            if volume.check_vol():
                vol_size = volume.get_size()
            else:
                vol_status = self.set_status(500, "Volume", vol_name, "Check_vol failed")

        return [vol_status], vol_size

    def create_clone(self, vol_name, uid, gid, clone_name, snapshot_name=None):
        '''Create clone of snapshot for a developer workspace'''
        volume = Volume(vol_name, self.aggregate)
        vol_size = ""

        if snapshot_name is None:
            status, error_message, clone = volume.make_clone_without_snapshot(clone_name,
                                                                              uid, gid)
        else:
            status, error_message, clone = volume.make_clone(snapshot_name, clone_name,
                                                             uid, gid)

        if status != "COMPLETED":
            if error_message == "Duplicate volume name %s.  (errno=17)" % clone_name:
                clone_status = self.set_status(200, "Clone", clone_name)
            else:
                clone_status = self.set_status(400, "Clone", clone_name, error_message)
                return [clone_status], vol_size
        else:
            clone_status = self.set_status(201, "Clone", clone_name)

        if clone.check_vol():
            status, error_message, junction_name = clone.mount()
            if status != "COMPLETED":
                junction_status = self.set_status(400, "Junction", junction_name, error_message)
                return [clone_status, junction_status], vol_size
            else:
                junction_status = self.set_status(201, "Junction", junction_name)

                if self.aggregate.check_vol_junction(clone_name, junction_name):
                    vol_size = volume.get_size()
                    return [clone_status, junction_status], vol_size

        else:
            clone_status = self.set_status(500, "Clone", clone_name, "Check_vol failed")
            return [clone_status], vol_size

    def create_snapshot(self, vol_name, snapshot_name):
        '''Create snapshot for a volume'''
        volume = Volume(vol_name, self.aggregate)
        status, error_message, _ = volume.make_snapshot(snapshot_name)
        if status != "COMPLETED":
            if error_message == "Failed to create snapshot %s of volume %s on Vserver %s. " \
                                "Reason: Snapshot already exists.  (errno=13020)" \
                                % (snapshot_name, vol_name, self.aggregate.svm_name):
                snap_status = self.set_status(200, "Snapshot", snapshot_name)
            else:
                snap_status = self.set_status(400, "Snapshot", snapshot_name, error_message)
        else:
            snap_status = self.set_status(201, "Snapshot", snapshot_name)
        return [snap_status]

    def get_size_used(self, volume_name):
        '''Retrieve storage usage for Admin Dashboard'''
        volume = Volume(volume_name, self.aggregate)
        # convert bytes to MB
        try:
            size_used = int(volume.get_size_used()) / (1024 * 1024)
        except KeyError:
            size_used = 0

        if size_used < 1024:
            storage = str(round(size_used, 2)) + "MB"
        else:
            # convert to GB
            size_used = size_used / 1024
            storage = str(round(size_used, 2)) + "GB"

        return storage

    # def get_total_storage(self, volumes):
    #     '''Return total storage usage for Admin Dashboard'''
    #     total = 0
    #     for vol in volumes:
    #         try:
    #             vol_name = helpers.replace_ontap_invalid_char(vol['name'])
    #             volume = Volume(vol_name, self.aggregate)
    #             size_used = int(volume.get_size_used()) / (1024 * 1024)
    #         except KeyError:
    #             size_used = 0
    #         total += size_used

    #     if total < 1024:
    #         storage_total = str(round(total, 2)) + "MB"
    #     else:
    #         # convert to GB
    #         total = total / 1024
    #         storage_total = str(round(total, 2)) + "GB"
    #     return storage_total

    def get_snapdiff_and_delete(self, volume_name, count):
        ''' delete workspace if greater than count days old with no changes'''
        volume = Volume(volume_name, self.aggregate)
        recent_snapshot, old_snapshot, error = self.get_oldest_and_latest_snapshots(
            volume_name, count)
        if error:
            return False, error
        if recent_snapshot is None or old_snapshot is None:
            logging.info("Workspace is less than %s days old", count)
            return False, "Workspace is less than %s days old" % count
        snapdiff = volume.get_snapdiff(recent_snapshot, old_snapshot)
        if snapdiff == 0:
            self.delete_volume(volume_name)
            logging.info("Deleted inactive workspace %s", volume_name)
            return True, "Workspace %s has been inactive for %s days\
                          and has been deleted" % (volume_name, count)
        # workspace is still active
        logging.info("Workspace %s is active", volume_name)
        return False, "Workspace %s is active" % volume_name

    def get_oldest_and_latest_snapshots(self, volume_name, days):
        '''
            Retrieve snapshot that is #days old and the most recent snapshot
            Returns: most_recent_snapshot, N_days_old_snapshot, Error(if any)
        '''
        snapshots = self.get_snapshot_list(volume_name)
        if snapshots is None:
            logging.info("get_snapshot_list returned 0 for volume %s", volume_name)
            return None, None, None
        if len(snapshots) < 2:
            logging.info("Workspace %s is less than %s days old", volume_name, days)
            return None, None, None
        # sort by timestamp: recent first, oldest last
        sorted_by_timestamp = sorted(snapshots, key=lambda snap: snap['timestamp'], reverse=True)
        most_recent_snapshot = sorted_by_timestamp[0]
        oldest_snapshot = None
        today = datetime.now()
        for snap in sorted_by_timestamp:
            snap_date = datetime.fromtimestamp(float(snap['timestamp']))
            delta = today - snap_date
            if delta.days > days:
                oldest_snapshot = snap
                break
        return most_recent_snapshot, oldest_snapshot, None

    def get_svm_list(self):
        '''Retrieve list of svms for ONTAP cluster'''
        data = self.api_server.get_svms()
        if not data:
            return []
        tmp = dict(data)
        svms = tmp['result']['records']
        return svms

    def get_aggregate_list(self):
        '''Retrieve list of aggregates for ONTAP cluster'''
        data = self.api_server.get_aggrs()
        if not data:
            return []
        tmp = dict(data)
        aggregates = tmp['result']['records']
        return aggregates

    def get_svm_aggregate_relationships(self):
        '''Retrieve list of svm/aggregate relationships for ONTAP cluster'''
        data = self.api_server.get_svm_aggregate_relationships()
        if not data:
            return []
        tmp = dict(data)
        aggregates = tmp['result']['records']
        return aggregates

    def get_aggregate_summary_list(self):
        ''' build list of (aggregate_name, svm_name)
            svm_name can be None if the aggregate is not associated with SVM '''
        aggregates = self.get_aggregate_list()
        svms = self.get_svm_list()
        relationships = self.get_svm_aggregate_relationships()
        svms_dict = dict()
        aggregates_list = list()
        for svm in svms:
            svms_dict[svm['key']] = svm['name']
        for aggregate in aggregates:
            found = False
            if aggregate['has_local_root']:
                # skip root aggregate
                logging.info("Skipping root aggregate %s", aggregate['name'])
                continue
            for relation in relationships:
                if relation['aggregate_key'] == aggregate['key']:
                    aggregates_list.append((aggregate['name'],
                                            svms_dict[relation['storage_vm_key']]))
                    found = True
                if not found:
                    # make sure the aggregate is listed \
                    # even with no svm is associated
                    aggregates_list.append((aggregate['name'], None))
        return aggregates_list

    def get_volume_list(self):
        '''Retrieve list of volumes for aggregate'''
        data = self.aggregate.get_volumes()
        if not data:
            return []
        tmp = dict(data)
        volumes = tmp['result']['records']
        return volumes

    def get_clone_list(self, volume_name):
        '''Retrieve list of clones for volume'''
        volume = Volume(volume_name, self.aggregate)
        data = volume.get_clones()
        if not data:
            return []
        tmp = dict(data)
        clones = tmp['result']['records']
        return clones

    def get_snapshot_list(self, volume_name):
        '''Retrieve list of snapshots for volume'''
        volume = Volume(volume_name, self.aggregate)
        data, error_message = volume.get_snapshots()
        if error_message:
            logging.error(error_message)
            return None, error_message
        if not data:
            return [], None
        tmp = dict(data)
        snaps = tmp['result']['records']
        return [{"snapshot_name": x['name'], "timestamp": x['access_timestamp']} for x in snaps]

    def delete_snapshot(self, volume_name, snapshot_name):
        '''Delete a snapshot, will fail if a clone is in use'''
        volume = Volume(volume_name, self.aggregate)
        status, error_message = volume.delete_snapshot(snapshot_name)
        if status == "COMPLETED":
            snap_status = self.set_status(201, "Snapshot", snapshot_name)
        else:
            if "has not expired or is locked" in error_message:
                logging.warn(
                    "Failed to delete snapshot %s. Most likely clone is in use. error: %s",
                    snapshot_name, error_message
                )
            else:
                logging.error(
                    "Failed to delete snapshot %s, unexpected error: %s",
                    snapshot_name, error_message
                )
            snap_status = self.set_status(400, "Snapshot", snapshot_name, error_message)
        return [snap_status]

    def delete_volume(self, volume_name):
        '''Delete a volume'''
        volume = Volume(volume_name, self.aggregate)
        snapshots = self.get_snapshot_list(volume_name)

        if snapshots is None:
            logging.error("get_snapshot_list for %s returned 0", volume_name)
        else:
            for snapshot in snapshots:
                #snapshot has snapshot_name and timestamp
                self.delete_snapshot(volume_name, snapshot['snapshot_name'])

        status, error, _ = volume.unmount_offline_delete_volume()

        if status == "COMPLETED":
            vol_status = self.set_status(201, "Volume", volume_name)
        else:
            vol_status = self.set_status(400, "Volume", volume_name, error)
        return [vol_status]

    def get_config_parameter(self, parameter):
        ''' Return value of specified config parameter '''
        return self.ontap_config[parameter] or ""

    @staticmethod
    def set_status(code, resource_type, resource_name, error=""):
        '''Create dictionary of resource status to return to server'''
        status = dict()
        status['resource'] = resource_type
        status['resource_name'] = resource_name
        status['code'] = code
        status['error_message'] = error
        if code == 200:
            status['status'] = "SUCCESS"
            status['message'] = "%s %s already exists" % (resource_type, resource_name)
        elif code == 201:
            status['status'] = "COMPLETED"
            status['message'] = "%s %s completed successfully" % (resource_type, resource_name)
        else:
            status['status'] = "FAILED"
            status['message'] = ""

        return status


    def modify_volume_ssl(self, volume_name, ssl_name):
        '''Modify the storage service level for volume'''
        volume = Volume(volume_name, self.aggregate)
        volume.modify_ssl(ssl_name)
