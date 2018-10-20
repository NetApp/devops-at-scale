'''Snapshot document tests'''
import unittest
from unittest.mock import patch, Mock
from web_service import create_app
import web_service.database.snapshot as snapshot
from web_service.database.snapshot import Snapshot

class TestSnapshot(unittest.TestCase):
    '''Test snapshot document class'''
    def setUp(self):
        app_settings = 'config.TestingConfig'
        self.app = create_app()
        self.app.config.from_object(app_settings)
        with self.app.app_context():
            self.app.testing = True

    def tearDown(self):
        pass

    @patch('web_service.helpers.helpers.connect_db')
    @patch('web_service.database.database.get_snapshots_by_volume')
    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_purge_db_inconsistency(self, mock_get_snapshot_list,
                                    mock_get_snapshots, mock_connect_db):
        '''Test deletion of inconsistent snapshots from DB'''
        mock_get_snapshots.return_value = [Mock(value='delete_me'), Mock(value='test_1')]
        mock_get_snapshot_list.return_value = [
        			 {"snapshot_name":"test_1", "timestamp":1500768910}], None
        count = snapshot.purge_inconsistent_snapshots(volume="test_volume")
        # delete_me is inconsistent
        self.assertEqual(count, 1)

    @patch('web_service.ontap.ontap_service.OntapService.delete_snapshot')
    @patch('web_service.helpers.helpers.connect_db')
    @patch('web_service.helpers.helpers.verify_successful_response')
    @patch('web_service.ontap.ontap_service.OntapService.get_snapshot_list')
    def test_purge_snapshots_by_volume(self, mock_get_snapshot_list,
                                       mock_helper, mock_connect_db, mock_del_snapshot):
        '''Test deletion of SCM snapshots'''
        mock_helper.return_value = True
        mock_get_snapshot_list.return_value = [
            {"snapshot_name":"test_1", "timestamp":100},
            {"snapshot_name":"test_2", "timestamp":200}], None
        count = snapshot.purge_snapshots_by_volume(volume="test_volume", purge_limit=1)
        mock_del_snapshot.assert_called_once_with('test_volume', 'test_1')
        # test_1 is deleted
        self.assertEqual(count, 1)

    @patch('web_service.database.snapshot.purge_snapshots_by_volume')
    @patch('web_service.database.snapshot.purge_inconsistent_snapshots')
    @patch('web_service.database.database.get_documents_by_type')
    @patch('web_service.helpers.helpers.connect_db')
    def test_purge_ci_snapshots(self, mock_connect_db, mock_get_documents,
                                mock_purge_inconsistent, mock_purge_by_volume):
        '''Test purge CI snapshots'''
        mock_get_documents.return_value = [{"name":"test",
                                            "volume": "test_vol",
                                            "ci_purge_limit": 50}]
        mock_purge_by_volume.return_value = 10
        result = snapshot.purge_ci_snapshots()
        self.assertEqual(result, 10)

    @patch('web_service.helpers.helpers.connect_db')
    def test_purge_snapshots_from_db(self, mock_connect_db):
        '''Test purging snapshots from DB'''
        mock_snapshot_row = Mock(value='test_1')
        inconsistent = snapshot.purge_snapshots_from_db(snapshots_ontap=[],
                                                        snapshots_db=[mock_snapshot_row])
        consistent = snapshot.purge_snapshots_from_db(snapshots_ontap=['test_1'],
                                                      snapshots_db=[mock_snapshot_row])
        # test_2 is deleted
        self.assertEqual(inconsistent, 1)
        self.assertEqual(consistent, 0)
