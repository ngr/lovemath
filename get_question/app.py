""" Get next question for flash-card.
"""
import random


__author__ = 'Nikolay Grishchenko'
__version__ = "1.00"

import logging
import time
import uuid

from components.lambda_api import LambdaApi
from sosw.app import LambdaGlobals, get_lambda_handler
from sosw.components.dynamo_db import DynamoDbClient


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class Processor(LambdaApi):
    """
    The main processor of get_question.
    """
    DEFAULT_CONFIG = {
        'init_clients':          ['DynamoDb'],
        'supported_operators':   ['-', '+'],
        'questions_per_session': 20,
        'dynamo_db_config':      {
            'row_mapper':      {
                'session':    'S',
                'created_at': 'N',
                'uid':        'N',
                'question':   'S',
                'answer':     'N',
                'correct':    'B',
            },
            'required_fields': ['session', 'created_at', 'uid'],
            'table_name':      'question',
            'hash_key':        'session'
        }
    }
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
            '/': {
                'GET':  {
                    'function':            self.ask_question,
                    'required_parameters': ['uid'],
                    'optional_parameters': ['name'],
                },
                'POST': {
                    'function':            self.post_answer,
                    'required_parameters': ['uid'],
                    'optional_parameters': ['name'],
                }
            }
        }


    def start_session(self, **kwargs):
        """
        You might want to implement saving a session somewhere in a separate table for example and/or
        to have a service for session handling. The current version just returns a generated session id.
        """

        sid = str(uuid.uuid4())
        return sid


    def ask_question(self, **kwargs):
        session = kwargs.get('session', self.start_session(**kwargs))

        a, b = self.generate_number(session), self.generate_number(session)
        result = {
            'a':          max(a, b),
            'b':          min(a, b),
            'operator':   random.choice(self.get_operator(session)),
            'session':    session,
            'qid':        str(uuid.uuid4()),  # Generate unique ID of question asked for future use.
            'created_at': time.time(),
        }

        # Stringify task for simply GUI.
        result['question'] = f"{result['a']} {result['operator']} {result['b']}"

        # Save asked question to DB
        self.dynamo_db_client.create(row=result)

        return result


    def post_answer(self, **kwargs):
        """
        Saves the result of submitted answer and returrns either next question or results.
        """

        keys = {
            'session': kwargs['session'],
            'qid':     kwargs['qid'],
        }

        question = self.dynamo_db_client.get_by_query(keys=keys)[0]

        question['answered_at'] = time.time()
        question['answer'] = kwargs.get('answer')
        question['correct'] = kwargs.get('answer') == eval(question['question'])

        self.dynamo_db_client.put(row=question)

        # Return next one if required or return result
        if self.questions_left(session=kwargs['session']):
            return self.ask_question(**kwargs)
        else:
            return self.get_results(**kwargs)


    def questions_left(self, **kwargs):
        """
        Return the number of questions left for this user in current session.
        :param kwargs:
        :return:
        """
        session = kwargs['session']
        return self.config['questions_per_session'] - \
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


    def generate_number(self, session):
        """ Supposed to get complexity based on user skills identified by ``session`` and generate a number. """
        return random.randint(0, 20)
        raise NotImplementedError()


    def get_operator(self, session):
        """ Supposed to get complexity based on user skills identified by ``session`` and return an operator. """
        return random.choice(self.config['supported_operators'])
        raise NotImplementedError()


global_vars = LambdaGlobals()
lambda_handler = get_lambda_handler(Processor, global_vars)
