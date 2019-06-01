''' Tests for ontap_service.py methods '''
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
import logging
import pytest
# from web_service.ontap.ontap_service import OntapService
# import web_service.tests.mocks as mocks

# Set project root directory so coverage.py can generate coverage
BASE_DIR = os.path.join(os.path.dirname(__file__), '../..')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

pytestmark = pytest.mark.skip("skipping as ONTAP APIs are not used directly thanks to Trident")


class TestONTAPService(unittest.TestCase):
    ''' Test ONTAP Service '''
    def setUp(self):
        api = {'api_server': 'ip-address.com', 'username': 'user', 'password': 'password'}
        self.ontap = OntapService(api['api_server'], api['username'], api['password'],
                                  'vserver-test', 'aggregate-test', '1.2.3.4')

    @patch('web_service.ontap.ontap_service.Volume.delete_snapshot')
    def test_delete_snapshot(self, mock_delete_snapshot):
        mock_delete_snapshot.return_value = 'COMPLETED', ''

        logging.basicConfig(level='INFO')
        volume_name = 'test_volume_for_ontap_services'
        [response] = self.ontap.delete_snapshot(volume_name, 'test_snapshot')

        self.assertEqual(response['code'], 201)

    @patch('logging.warning')
    @patch('web_service.ontap.ontap_service.Volume.delete_snapshot')
    def test_delete_snapshot_fail(self, mock_delete_snapshot, mock_logger):
        ''' Log ONTAP delete error if snapshot is active '''
        mock_delete_snapshot.return_value = 'FAILED', 'snapshot has not expired or is locked'

        logging.basicConfig(level='WARNING')
        volume_name = 'test_volume_for_ontap_services'
        [response] = self.ontap.delete_snapshot(volume_name, 'test_snapshot')

        mock_logger.assert_called_with(
            'Failed to delete snapshot %s. Most likely clone is in use. error: %s',
            'test_snapshot', 'snapshot has not expired or is locked'
        )
        self.assertEqual(response['code'], 400)

    @patch('logging.error')
    @patch('web_service.ontap.ontap_service.Volume.delete_snapshot')
    def test_delete_snapshot_fail_other(self, mock_delete_snapshot, mock_logger):
        ''' Log ONTAP delete error for other reasons '''
        mock_delete_snapshot.return_value = 'FAILED', 'other error'

        logging.basicConfig(level='WARNING')
        volume_name = 'test_volume_for_ontap_services'
        [response] = self.ontap.delete_snapshot(volume_name, 'test_snapshot')

        mock_logger.assert_called_with(
            'Failed to delete snapshot %s, unexpected error: %s', 'test_snapshot', 'other error'
        )
        self.assertEqual(response['code'], 400)

    @patch('web_service.ontap.ontap_service.OntapService.delete_volume')
    @patch('web_service.ontap.ontap_service.Volume.get_snapdiff')
    @patch('web_service.ontap.ontap_service.OntapService.get_oldest_and_latest_snapshots')
    def test_get_snapdiff_and_delete(self, mock_get_oldest_latest_snapshots, mock_get_snapdiff, mock_delete_volume):
        mock_delete_volume.return_value = mocks.CREATE_VOL_RETURN_VAL
        mock_get_snapdiff.return_value = 0
        mock_get_oldest_latest_snapshots.return_value = ('weekly.5678', '1503002079'), ('weekly.1234', '1503002065')

        deleted, message = self.ontap.get_snapdiff_and_delete('test', 100)
        self.assertEqual(deleted, True)
        self.assertTrue("test has been inactive for" in message)

    @patch('web_service.ontap.ontap_service.Volume.get_snapdiff')
    @patch('web_service.ontap.ontap_service.OntapService.get_oldest_and_latest_snapshots')
    def test_get_snapdiff_and_delete_active(self, mock_get_oldest_latest_snapshots, mock_get_snapdiff):
        mock_get_snapdiff.return_value = 1
        mock_get_oldest_latest_snapshots.return_value = ('weekly.5678', '1503002079'), ('weekly.1234', '1503002065')

        deleted, message = self.ontap.get_snapdiff_and_delete('test', 2)
        self.assertEqual(deleted, False)
        self.assertTrue("test is active" in message)

    @patch('web_service.ontap.ontap_service.OntapService.get_oldest_and_latest_snapshots')
    def test_get_snapdiff_and_delete_new(self, mock_get_oldest_latest_snapshots):
        mock_get_oldest_latest_snapshots.return_value = None, None
        deleted, message = self.ontap.get_snapdiff_and_delete('test', 2)
        self.assertEqual(deleted, False)
        self.assertTrue("Workspace is less than" in message)

    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_get_oldest_and_latest_snapshots(self, mock_get_snapshot_list):
        today = datetime.now()
        two_days_old_epoch = (today - timedelta(days=2)).strftime('%s')
        today_epoch = today.strftime('%s')
        two_days_snap = ('two_days_old', two_days_old_epoch)
        today_snap = ('today', today_epoch)
        mock_get_snapshot_list.return_value = [
            two_days_snap,
            today_snap,
        ], ""

        recent, old = self.ontap.get_oldest_and_latest_snapshots('test', 1)
        self.assertEqual(two_days_snap, old)
        self.assertEqual(today_snap, recent)

    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_get_oldest_and_latest_snapshots_none(self, mock_get_snapshot_list):
        today = datetime.now()
        one_day_old_epoch = (today - timedelta(days=1)).strftime('%s')
        today_epoch = today.strftime('%s')
        one_day_snap = ('one_day_old', one_day_old_epoch)
        today_snap = ('today', today_epoch)
        mock_get_snapshot_list.return_value = [
            one_day_snap,
            today_snap,
        ], ""

        recent, old = self.ontap.get_oldest_and_latest_snapshots('test', 1)
        self.assertEqual(None, old)
        self.assertEqual(today_snap, recent)

    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_get_oldest_and_latest_snapshots_empty(self, mock_get_snapshot_list):
        today = datetime.now()
        one_day_old_epoch = (today - timedelta(days=1)).strftime('%s')
        today_epoch = today.strftime('%s')
        one_day_snap = ('one_day_old', one_day_old_epoch)
        today_snap = ('today', today_epoch)
        mock_get_snapshot_list.return_value = None, "some error message"

        recent, old = self.ontap.get_oldest_and_latest_snapshots('test', 1)
        self.assertIsNone(old)
        self.assertIsNone(recent)


if __name__ == "__main__":
    unittest.main()
