__name__ = 'get_question'

import boto3
import datetime
import logging
import unittest
from unittest.mock import patch
import os

from collections import defaultdict

os.environ["STAGE"] = "test"
os.environ["autotest"] = "True"

from get_question.app import Processor


logging.getLogger('botocore').setLevel(logging.WARNING)


class get_question_TestCase(unittest.TestCase):

    def setUp(self):
        """
        setUp TestCase.
        """

        self.get_config_patcher = patch.object(Processor, 'get_config')
        self.get_config_mock = self.get_config_patcher.start()
        self.get_config_mock.return_value = {}

        CONFIG = {
            'custom': 1,
        }
        self.processor = Processor(test=True, custom_config=CONFIG)


    def tearDown(self):
        """
        """

        # We have to kill processor first of all, otherwise it keeps connection alive.
        # If not processor - no problem. :)
        try:
            del self.processor
        except:
            pass

        self.get_config_patcher.stop()


    def test_true(self):
        """
        Sample test.
        """
        self.assertTrue(True)
