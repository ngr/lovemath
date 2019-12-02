__name__ = 'get_question'

import boto3
import datetime
import logging
import unittest
from unittest.mock import MagicMock, patch
import os

from collections import defaultdict


os.environ["STAGE"] = "test"
os.environ["autotest"] = "True"

from get_question.app import Processor


logging.getLogger('botocore').setLevel(logging.WARNING)


class get_question_TestCase(unittest.TestCase):
    TEST_CONFIG = {
        'dynamo_db_config': {
            'table_name': 'autotest_sale_log'
        },
    }

    SAMPLE_ANSWER_CORRECT = {'question': '2 + 2', 'answer': '4', 'session': 'foo'}

    def setUp(self):
        """
        setUp TestCase.
        """

        self.get_config_patcher = patch.object(Processor, 'get_config')
        self.get_config_mock = self.get_config_patcher.start()
        self.get_config_mock.return_value = {}

        self.boto3_patch = patch("boto3.client")
        self.boto3_mock = self.boto3_patch.start()

        self.processor = Processor(test=True, custom_config=self.TEST_CONFIG)
        self.processor.dynamo_db_client = MagicMock()


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


    def test_post_answer__validate_result(self):
        TESTS = {
            '42 - 42': 0,
            '42 + 42': 84,
            '42 - 2':  40,
        }

        for question, answer in TESTS.items():
            self.processor.post_answer(**{'question': question, 'answer': answer, 'session': 'foo'})
            args, kwargs = self.processor.dynamo_db_client.create.call_args
            self.assertTrue(kwargs['row']['correct'])


    def test_post_answer__validate_result__incorrect(self):
        TESTS = {
            '42 - 42': 1,
            '42 + 42': 1,
            '42 - 2':  1,
        }

        for question, answer in TESTS.items():
            self.processor.post_answer(**{'question': question, 'answer': answer, 'session': 'foo'})
            args, kwargs = self.processor.dynamo_db_client.create.call_args
            self.assertFalse(kwargs['row']['correct'])


    def test_post_answer__continues_questions_left(self):
        self.processor.questions_left = MagicMock(return_value=5)

        result = self.processor.post_answer(**self.SAMPLE_ANSWER_CORRECT)
        self.processor.questions_left.assert_called_once()

        # Expecting regular get_question response returned from post_answer
        EXPECTED = ['question', 'qid', 'session', 'a', 'b', 'operator', 'created_at']
        for key in EXPECTED:
            self.assertIsNotNone(result.get(key), f"Missing {key} in result")
