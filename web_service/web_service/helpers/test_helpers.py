import os
import sys
import unittest
from unittest.mock import patch, Mock
import web_service.helpers.helpers as ut

# Set project root directory so coverage.py can generate coverage
BASE_DIR = os.path.join(os.path.dirname(__file__), '../..')
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestHelpersMethods(unittest.TestCase):
    """ Test Kubernetes API """

    def setUp(self):
        pass

    @patch('web_service.helpers.helpers._setup_couchdb')
    def test_onetime_setup(self, mock_setup):
        """ Test helper to call setup_couchdb once """
        ut.onetime_setup_required()
        mock_setup.assert_called_once_with()
