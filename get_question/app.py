""" Get next question for flash-card.
"""

__author__ = 'Nikolay Grishchenko'
__version__ = "1.00"

import logging

from sosw import Processor as SoswProcessor
from sosw.app import LambdaGlobals, get_lambda_handler

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class Processor(SoswProcessor):
    """
    The main processor of get_question.
    """
    DEFAULT_CONFIG = {}


    def __call__(self, event):
        """
        Call the Processor.
        """

        result = {"hello": "world"}

        # Do some basic cleaning and closing `sosw` task.
        super().__call__(event)

        return result

global_vars = LambdaGlobals()
lambda_handler = get_lambda_handler(Processor, global_vars)

