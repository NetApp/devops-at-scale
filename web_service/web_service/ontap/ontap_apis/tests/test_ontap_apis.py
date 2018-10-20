''' python wrappers arounf NetApp API services (NSLM) '''

import unittest
import random
import string
import requests

from .. import ontap_apis as uut
# import api_servers as uut

VSM_NAME = 'sdot-development-vserver01'
AGGR_NAME = 'node01_aggr01'
VOLUME_NAME = 'unittest_to_delete'
SNAPSHOT_NAME = 'unittest_snapshot_to_delete'

class TestAPIBaseClass(unittest.TestCase):
    ''' Test API Base class '''
    def setUp(self):
        ''' credentials used throughout these tests '''
        apiuser = 'admin'
        apipass = 'Password@123'
        api = '169.47.240.185:8443'
        self.api_server = uut.APIServer(api, apiuser, apipass)
        self.aggregate = uut.Aggregate(VSM_NAME, AGGR_NAME, self.api_server)

    def create_temp_volume(self, name):
        ''' utility function to create a volume.
            make sure to delete it
        '''
        uid = 1000
        gid = 1000
        size = 23
        volume = uut.Volume(name, self.aggregate)
        response, error_message = volume.make_volume(
            size,
            uid,
            gid)
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(volume.check_vol())
        self.assertEqual(volume.volume_name, name)
        return volume

    def delete_temp_volume(self, volume):
        ''' delete temp vol '''
        self.assertTrue(volume.check_vol())
        response, error_message = volume.unmount()
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        response, error_message = volume.offline_volume()
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        response, error_message = volume.delete_volume()
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.assertFalse(volume.check_vol())

    def delete_temp_volume_if_present(self, name):
        volume = uut.Volume(name, self.aggregate)
        if volume.check_vol():
            self.delete_temp_volume(volume)

    @staticmethod
    def return_random_string(length):
        rand_str_func = lambda n: ''.join([random.choice(string.ascii_lowercase) for i in range(n)])
        rand_str = rand_str_func(length)
        return rand_str

class TestAPIMethods(TestAPIBaseClass):
    ''' positive test for ONTAP APIs using NSLM '''

    def test_get_volume(self):
        ''' test list volume '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response = self.aggregate.get_volumes()
        tmp = dict(response)
        vols = tmp['result']['records']
        names = [i['name'] for i in vols]
        self.assertIn(test_volume_name, names)
        self.delete_temp_volume(volume)

    def test_get_volume_clones(self):
        ''' create two clones for given volume and ensure Volume.get_clones() lists both clones'''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_clone_two_name = "%s_clone_two_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, _, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertEqual(response, "COMPLETED")
        response, _, clone_two = volume.make_clone(
            test_snapshot_name,
            test_clone_two_name,
            "",
            "")
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(clone.check_vol())
        self.assertTrue(clone_two.check_vol())
        response = volume.get_clones()
        tmp = dict(response)
        vols = tmp['result']['records']
        names = [i['name'] for i in vols]
        self.assertIn(test_clone_name, names)
        self.assertIn(test_clone_two_name, names)
        clone.offline_volume()
        clone.delete_volume()
        clone_two.offline_volume()
        clone_two.delete_volume()
        self.delete_temp_volume(volume)

    def test_get_aggrs(self):
        ''' assuming node01_aggr01 already exists '''
        response = self.api_server.get_aggrs()
        tmp = dict(response)
        aggrs = tmp['result']['records']
        names = [i['name'] for i in aggrs]
        self.assertIn('node01_aggr01', names)

    def test_get_snapshots(self):
        ''' test list snapshots '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message = volume.get_snapshots()
        self.assertEqual(error_message, "")
        tmp = dict(response)
        aggrs = tmp['result']['records']
        names = [i['name'] for i in aggrs]
        self.assertEqual(len(names), 1)
        self.delete_temp_volume(volume)

    def test_get_size_used(self):
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        size_used = volume.get_size_used()
        # temp volume size = 23MB
        self.assertLess(size_used, uut.get_size(23))
        self.delete_temp_volume(volume)

    def test_get_svms(self):
        ''' assuming sdot-development-vserver01 already exists '''
        response = self.api_server.get_svms()
        tmp = dict(response)
        svms = tmp['result']['records']
        names = [i['name'] for i in svms]
        self.assertIn('sdot-development-vserver01', names)

    def test_get_export_policies(self):
        ''' assuming default export policy already exists '''
        response = self.api_server.get_export_policies()
        tmp = dict(response)
        policies = tmp['result']['records']
        names = [i['name'] for i in policies]
        self.assertIn('default', names)

    def test_get_uid_gid(self):
        ''' test get uid gid '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response = volume.get_uid_gid()
        expected_response = {
            'uid': '1000',
            'gid': '1000'
        }
        self.assertEqual(response, expected_response)
        self.delete_temp_volume(volume)

    def test_get_size(self):
        ''' check size is multiplied by 1024 * 1024 '''
        response = uut.get_size(100)
        self.assertEqual(100 * 1024 * 1024, response)

    def test_get_key_aggr(self):
        ''' assuming node01_aggr01 already exists '''
        response = self.aggregate.get_key_aggr()
        self.assertIn('3b108cbe-301e-11e7-a2c3-005056815d0c:type=aggregate',
                      response)

    def test_get_key_vol(self):
        ''' assuming gitlab_helm_gitlab_ce_data already exists '''
        volume = uut.Volume('gitlab_helm_gitlab_ce_data', self.aggregate)
        response = volume.get_key_vol()
        self.assertIn('3b108cbe-301e-11e7-a2c3-005056815d0c:type=volume',
                      response)

    def test_get_key_svm(self):
        ''' assuming sdot-development-vserver01 already exists '''
        response = self.aggregate.api_server.get_key_svm(self.aggregate.svm_name)
        self.assertIn('3b108cbe-301e-11e7-a2c3-005056815d0c:type=vserver',
                      response)

    def test_get_key_export_policy(self):
        ''' assuming default export policy already exists '''
        response = self.aggregate.api_server.get_key_export_policy("default")
        self.assertIn('07e4e37e-2bab-11e5-8836-00a0981a51c0:type=export_policy',
                      response)

    def test_check_vol(self):
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response = volume.check_vol()
        self.delete_temp_volume(volume)
        self.assertTrue(response)

    def test_check_snapshot(self):
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response = volume.check_snapshot(test_snapshot_name)
        self.delete_temp_volume(volume)
        self.assertTrue(response)

    def test_get_jpath(self):
        ''' get junction path test '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response = volume.get_jpath()
        self.delete_temp_volume(volume)
        self.assertEqual("/%s" % test_volume_name, response)

    def test_make_new_volume(self):
        ''' make vol test '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        uid = 1000
        gid = 1000
        size = 23
        volume = uut.Volume(test_volume_name, self.aggregate)
        response, error_message = volume.make_volume(
            size,
            uid,
            gid)
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(volume.check_vol())
        self.assertEqual(volume.volume_name, test_volume_name)

        # cleanup
        self.delete_temp_volume(volume)

    def test_make_snapshot(self):
        ''' make snapshot test '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response, _, _ = volume.make_snapshot(test_snapshot_name)
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(volume.check_snapshot(test_snapshot_name))
        self.delete_temp_volume(volume)

    def test_make_snapshot_existing(self):
        ''' make snapshot test - duplicate Snapshot '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        response, error_message, snapshot = volume.make_snapshot(test_snapshot_name)
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(volume.check_snapshot(test_snapshot_name))
        response, error_message, snapshot = volume.make_snapshot(test_snapshot_name)
        self.assertEqual(response, "FAILED")
        self.assertEqual(
            error_message,
            "Failed to create snapshot %s of "
            "volume %s on Vserver "
            "sdot-development-vserver01. Reason: Snapshot already exists.  (errno=13020)" %
            (test_snapshot_name, test_volume_name))
        self.assertTrue(volume.check_snapshot(test_snapshot_name))
        self.assertEqual(snapshot.volume_name, test_snapshot_name)
        self.delete_temp_volume(volume)

    def test_make_clone(self):
        ''' make clone test '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, _, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertEqual(response, "COMPLETED")
        self.assertTrue(clone.check_vol())
        self.assertEqual(clone.volume_name, test_clone_name)
        clone.offline_volume()
        clone.delete_volume()
        self.delete_temp_volume(volume)

    def test_mount_clone(self):
        ''' mount clone test '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        self.assertEqual(clone.volume_name, test_clone_name)
        response, error_message, junction_path = clone.mount()
        self.assertEqual(response, "COMPLETED")
        self.assertEqual(error_message, "")
        self.assertEqual(junction_path, "/%s" % test_clone_name)
        clone.unmount()
        clone.offline_volume()
        clone.delete_volume()
        self.delete_temp_volume(volume)

    def test_set_volume_state(self):
        ''' offline volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)

        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        response, error_message = clone.unmount()
        response, error_message = clone.offline_volume()
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        clone.delete_volume()
        self.delete_temp_volume(volume)

class TestAPIMethodsDelete(TestAPIBaseClass):
    ''' positive test for ONTAP APIs using NSLM '''

    def test_delete_snapshot(self):
        ''' delete snapshot '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        status, _, _ = volume.make_snapshot(test_snapshot_name)
        self.assertEqual(status, "COMPLETED")
        self.assertTrue(volume.check_snapshot(test_snapshot_name))
        status, error_message = volume.delete_snapshot(test_snapshot_name)
        self.assertEqual(error_message, "")
        self.assertEqual(status, "COMPLETED")
        self.delete_temp_volume(volume)

    def test_delete_clone(self):
        ''' delete volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        response, error_message = clone.offline_volume()
        response, error_message = clone.delete_volume()
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.delete_temp_volume(volume)

    def test_delete_mounted_clone(self):
        ''' delete mounted volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        clone.mount()
        clone.unmount()
        clone.offline_volume()
        response, error_message = clone.delete_volume()
        self.assertFalse(clone.check_vol())
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.delete_temp_volume(volume)

    def test_delete_mounted_clone_all(self):
        ''' delete mounted volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        _, _, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        clone.mount()
        status, error_message, _ = clone.unmount_offline_delete_volume()
        self.assertFalse(clone.check_vol())
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message, "")
        self.assertEqual(status, "COMPLETED")
        self.delete_temp_volume(volume)

    def test_delete_unmounted_clone(self):
        ''' delete unmounted volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        response, error_message, _ = clone.unmount_offline_delete_volume()
        self.assertFalse(clone.check_vol())
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message, "")
        self.assertEqual(response, "COMPLETED")
        self.delete_temp_volume(volume)

    def test_delete_volume_clones(self):
        ''' create two clones for given volume and ensure
            Volume.delete_all_clones() deletes all clones '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_clone_two_name = "%s_clone_two_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, _, _ = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        response, _, _ = volume.make_clone(
            test_snapshot_name,
            test_clone_two_name,
            "",
            "")
        response = volume.get_clones()
        tmp = dict(response)
        vols = tmp['result']['records']
        names = [i['name'] for i in vols]
        self.assertEqual(len(names), 2)
        deleted_clones, undeleted_clones = volume.delete_all_clones()
        self.assertEqual(len(deleted_clones), 2)
        self.assertEqual(len(undeleted_clones), 0)
        response = volume.get_clones()
        tmp = dict(response)
        vols = tmp['result']['records']
        names = [i['name'] for i in vols]
        self.assertEqual(len(names), 0)
        self.delete_temp_volume(volume)

class TestAPIMethodsNegativeNoAccess(TestAPIBaseClass):
    ''' negative testcases, wrong credentials or wrong IP/port '''

    def test_get_volume(self):
        ''' unknown user '''
        apiuser = 'dummy'
        apipass = 'Password@123'
        api = '169.47.240.185:8443'
        api_server = uut.APIServer(api, apiuser, apipass)
        aggregate = uut.Aggregate(VSM_NAME, AGGR_NAME, api_server)
        with self.assertRaises(requests.ConnectionError) as exc:
            _ = aggregate.get_volumes()
        self.assertEqual(str(exc.exception), "ERROR: status = 401 - Invalid credentials?")

    def test_get_volume_bp(self):
        ''' bad password '''
        apiuser = 'admin'
        apipass = 'Password@1234'
        api = '169.47.240.185:8443'
        api_server = uut.APIServer(api, apiuser, apipass)
        aggregate = uut.Aggregate(VSM_NAME, AGGR_NAME, api_server)
        with self.assertRaises(requests.ConnectionError) as exc:
            _ = aggregate.get_volumes()
        self.assertEqual(str(exc.exception), "ERROR: status = 401 - Invalid credentials?")


    def test_get_volume_burl(self):
        ''' bad port '''
        apiuser = 'admin'
        apipass = 'Password@123'
        api = '169.47.240.185:8446'
        api_server = uut.APIServer(api, apiuser, apipass)
        aggregate = uut.Aggregate(VSM_NAME, AGGR_NAME, api_server)
        with self.assertRaises(requests.ConnectionError) as exc:
            _ = aggregate.get_volumes()
        needle = str(exc.exception).split(':', 1)[0]
        self.assertEqual(
            needle,
            "HTTPSConnectionPool(host='%s', port=%s)" % tuple(api.split(':')))

class TestAPIMethodsNegative(TestAPIBaseClass):
    ''' negative testcases '''

    def test_make_existing_volume(self):
        ''' volume already exists '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        uid = 1000
        gid = 1000
        size = 23
        self.delete_temp_volume_if_present(test_volume_name)
        self.create_temp_volume(test_volume_name)

        # attempt to create one more time
        volume = uut.Volume(test_volume_name, self.aggregate)
        response, error_message = volume.make_volume(
            size,
            uid,
            gid)
        self.assertEqual(response, "FAILED")
        self.assertEqual(error_message,
                         "Duplicate volume name %s.  (errno=17)"% test_volume_name)
        self.assertTrue(volume.check_vol())
        self.assertEqual(volume.volume_name, test_volume_name)

        # cleanup
        self.delete_temp_volume(volume)

    def test_delete_mounted_clone_fail(self):
        ''' delete volume or clone '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertTrue(clone.check_vol())
        clone.mount()
        response, error_message = clone.offline_volume()
        self.assertTrue(volume.check_vol())
        self.assertEqual(error_message,
                         "Volume %s on Vserver sdot-development-vserver01 must be unmounted " \
                         "before being taken offline or restricted.  (errno=160)" % test_clone_name)
        self.assertEqual(response, "FAILED")
        response, error_message = clone.unmount()
        response, error_message = clone.offline_volume()
        response, error_message = clone.delete_volume()
        self.delete_temp_volume(volume)

    def test_create_volume_bad_aggr(self):
        ''' create vol invalid aggr '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        uid = 1000
        gid = 1000
        size = 23
        aggregate = uut.Aggregate(VSM_NAME, 'dummy_aggr', self.api_server)
        volume = uut.Volume(test_volume_name, aggregate)
        status, error_message = volume.make_volume(
            size,
            uid,
            gid)
        self.assertEqual(status, "FAILED")
        self.assertEqual(
            error_message,
            "Missing value for zapi field: containing-aggr-name.  (errno=13001)")

    def test_create_volume_bad_svm(self):
        ''' create vol invalid svm '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        uid = 1000
        gid = 1000
        size = 23
        aggregate = uut.Aggregate('dummy-vserver-xxx', AGGR_NAME, self.api_server)
        volume = uut.Volume(test_volume_name, aggregate)
        status, error_message = volume.make_volume(
            size,
            uid,
            gid)
        self.assertEqual(status, "FAILED")
        self.assertEqual(
            error_message,
            "Could not find storage container object in the service context")

    def test_make_clone_existing(self):
        ''' should return 202 but not create clone because it is a duplicate name '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_clone_name = "%s_clone_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)

        volume = self.create_temp_volume(test_volume_name)
        volume.make_snapshot(test_snapshot_name)
        volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        response, error_message, clone = volume.make_clone(
            test_snapshot_name,
            test_clone_name,
            "",
            "")
        self.assertEqual(response, "FAILED")
        self.assertEqual(
            error_message,
            "Duplicate volume name %s.  (errno=17)" % test_clone_name)
        self.assertTrue(clone.check_vol())
        self.assertEqual(clone.volume_name, test_clone_name)
        clone.offline_volume()
        clone.delete_volume()
        self.delete_temp_volume(volume)

class TestAPIMethodsNegativeDelete(TestAPIBaseClass):
    ''' negative testcases '''

    def test_delete_with_snapshot(self):
        ''' delete volume with existing snapshot '''
        rand_str = self.return_random_string(5)
        test_volume_name = "%s_vol_%s" % (self._testMethodName, rand_str)
        test_snapshot_name = "%s_snap_%s" % (self._testMethodName, rand_str)
        volume = self.create_temp_volume(test_volume_name)
        status, _, _ = volume.make_snapshot(test_snapshot_name)
        self.assertEqual(status, "COMPLETED")
        self.assertTrue(volume.check_snapshot(test_snapshot_name))
        status, error_message = volume.unmount()
        self.assertEqual(error_message, "")
        self.assertEqual(status, "COMPLETED")
        status, error_message = volume.offline_volume()
        self.assertEqual(error_message, "")
        self.assertEqual(status, "COMPLETED")
        status, error_message = volume.delete_volume()
        self.assertEqual(error_message, "")
        self.assertEqual(status, "COMPLETED")


if __name__ == '__main__':
    unittest.main()
