""" Get next question for flash-card.
"""

__author__ = 'Nikolay Grishchenko'
__version__ = "1.00"

import logging

from components.lambda_api import LambdaApi
from sosw.app import LambdaGlobals, get_lambda_handler
from sosw.components.dynamo_db import DynamoDbClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class Processor(LambdaApi):
    """
    The main processor of get_question.
    """
    DEFAULT_CONFIG = {}
    dynamo_db_client: DynamoDbClient = None


    def __call__(self, event):
        """
        Call the Processor.
        """

        result = {"hello": "world"}

        # Do some basic cleaning and closing `sosw` task.
        super().__call__(event)

        return result


    def get_router(self):
        return {
            '/':  {
                'GET': {
                    'function': self.get_question,
                    'required_parameters': ['uid'],
                    'optional_parameters': ['name'],
                },
                'POST': {
                    'function': self.post_question,
                    'required_parameters': ['uid'],
                    'optional_parameters': ['name'],
                }
            }
        }


    def get_question(self, **kwargs):
        return {"Think about the structure": 1}


    def post_question(self, **kwargs):

        # Save the current result of submitted question.
        result = kwargs
        self.dynamo_db_client.put(result)

        # Return next one if required or return result
        if self.questions_left():
            return self.get_question(**kwargs)
        else:
            return self.get_results(**kwargs)


    def questions_left(self, **kwargs):
        """
        Return the number of questions left for this user in current session.
        :param kwargs:
        :return:
        """
        session = kwargs['session']
        self.dynamo_db_client.get_by_query({"session": session}, return_count=True)


    def get_results(self, **kwargs):
        session = kwargs['session']
        results = self.dynamo_db_client.get_by_query({"session": session}, fetch_all_fields=True)
        return results


    def is_authenticated(self, api_token=None, env='production'):
        """
        Need to implement with Cognito.
        LambdaAPI currently supports only the external proprietary auth endpoint.

        Current version for my Mark bypasses auth mechanism.
        """
        return True


global_vars = LambdaGlobals()
lambda_handler = get_lambda_handler(Processor, global_vars)

