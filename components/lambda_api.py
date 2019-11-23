"""
Abstract HTTP API endpoint for writing tracking data.

..  note::

    The following packages are required for the component to work in your Lambda:

    - requests
"""

__name__ = 'lambda_api'
__author__ = 'Sophie Fogel'
__version__ = "1.00"

__all__ = ['LambdaApi', 'RequestValidationException', 'AuthenticationError']

import time
import logging
import requests
import json

from sosw import Processor
from sosw.components.decorators import logging_wrapper

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class RequestValidationException(Exception):
    pass


class AuthenticationError(Exception):
    pass


class LambdaApi(Processor):

    api_tokens_cache = {}
    allowed_param_sources = ('qs', 'data')

    def __init__(self, custom_config=None, **kwargs):
        super().__init__(custom_config=custom_config, **kwargs)

        if 'auth_header' not in self.config:
            self.config['auth_header'] = 'api_token'

        admin_api_urls = self.get_config('admin_api_urls')
        self.config.update({'auth_url': admin_api_urls.get('auth')})


    # add prefixes to support different endpoints: for example add '/admin' prefix to support both /wing & /admin/wing
    path_prefixes = []


    def __call__(self, event):
        logger.info(f"Called the {self.__class__.__name__}")
        try:
            return self.process_event(event)
        except RequestValidationException as e:
            self.stats['invalid_requests_errors'] += 1
            return {
                "statusCode": 400,
                "headers":    {
                    'Access-Control-Allow-Origin': '*',
                    'Content-type':                'application/json',
                    'Accept':                      'text/plain'
                },
                'body':       json.dumps({"Error": str(e)})
            }
        except AuthenticationError:
            self.stats['unauthenticated_requests_errors'] += 1
            return {
                'statusCode': 401,
                'body':       json.dumps({"message": "Authentication error, token is missing or invalid."}),
                'headers':    {
                    'Content-type': 'application/json'
                },
            }


    def process_event(self, event):

        self.handle_authentication(event)

        qs_parameters = event.get("queryStringParameters", {}) or {}

        full_path = self.strip_req_path(event['path'])
        method = event.get('httpMethod', 'GET').upper()
        request_data_dict = self.get_request_data(event) or {}

        all_params = {**qs_parameters, **request_data_dict}
        self.router = self.get_router()

        # API Gateway can have a custom domain, then the path can have some prefix, e.g. '/admin'.
        # Here we try different path prefixes to find if any of them match the request.
        path = full_path
        path_prefixes = list(set([''] + (self.path_prefixes or [])))

        for path_prefix in path_prefixes:
            if full_path.startswith(path_prefix):
                path = full_path[len(path_prefix):]
                path = path.rstrip('/')
                if path and path in self.router:
                    break

        if path not in self.router:
            msg = f"Request path `{full_path}` is not supported."
            if path_prefixes:
                msg += f" Tried path prefixes, {path_prefixes}"
            raise RequestValidationException(msg)

        if method not in self.router[path]:
            raise RequestValidationException(f"Request method {method} is not supported for path {path}")

        router_target = self.router[path][method]
        logger.info(f"For path {path} and method {method}, got router_target: {router_target}")

        func = router_target['function']
        required_parameters = router_target.get('required_parameters', [])
        optional_parameters = router_target.get('optional_parameters', [])
        all_parameters = required_parameters + optional_parameters

        allowed_param_sources = router_target.get('allowed_param_sources') or self.allowed_param_sources
        if qs_parameters and 'qs' not in allowed_param_sources:
            raise RequestValidationException(f"QueryString parameters are not allowed")
        if qs_parameters and 'data' not in allowed_param_sources:
            raise RequestValidationException(f"Request Data parameters are not allowed")

        parameters_dict = {}

        # Check that we didn't get any unwanted url parameters
        if all_params:
            for param in all_params:
                if param not in all_parameters:
                    raise RequestValidationException(
                        f"Received unsupported parameter (either in query string or in data): {param}.")

        # Collect parameter values
        for parameter_name in all_parameters:
            parameter_value = None if all_params is None else all_params.get(parameter_name)
            if parameter_value is not None:
                parameters_dict[parameter_name] = parameter_value

        # Check if a parameter is missing
        for p in required_parameters:
            if p not in parameters_dict:
                raise RequestValidationException(f"Missing a required parameter: {p}")

        logger.info(f"Calling {func} with parameters {parameters_dict}")

        try:
            data = func(**parameters_dict)

        except Exception as e:
            logger.exception(f"{self.__class__.__name__} call failed.")
            data = {"Error": f"{e}"}

        # if not isinstance(data, (str, dict)):
        #     data = self.sql_model_to_dict_or_list(data)

        res = {
            "statusCode": self.get_status_code(data=data),
            "headers":    {
                'Access-Control-Allow-Origin':  '*',
                'Access-Control-Allow-Headers': 'api_token, env',
                'Content-type':                 'application/json',
                'Accept':                       'text/plain'
            },
            'body':       json.dumps(data or {})
        }

        return res


    def handle_authentication(self, event):
        headers = event.get('headers') or {}
        api_token = headers.pop('api_token', None)
        env = headers.pop('env', 'production')
        logger.info(f"Checking if user is authenticated. api_token: {api_token}. env: {env}")

        is_authenticated = self.is_authenticated(api_token, env)
        logger.info(f"User is {'not ' if not is_authenticated else ''}authenticated.")
        if not is_authenticated:
            raise AuthenticationError


    def is_authenticated(self, api_token, env='production'):
        """
        :param api_token: User api token.
        :rtype: bool
        """

        if self.is_authentication_cached(api_token, env):
            return True

        url = self.config.get('auth_url')
        headers = {'api_token': api_token, 'env': env}
        logger.info(f"Checking if user is authenticated. Sending GET request to `{url}` with headers {headers}")
        response = requests.get(url, headers=headers)
        try:
            data = response.json()
            result = data['is_authenticated']
            if result is True:
                self.api_tokens_cache[api_token] = {'env': env,
                                                    'expires': time.time() + self.config.get('auth_token_ttl', 60)}
            return result
        except:
            logger.exception(f"Authentication failed - received bad response from auth endpoint.")
            return False


    def is_authentication_cached(self, api_token, env='production'):
        cached_token = self.api_tokens_cache.get(api_token)
        try:
            if cached_token['env'] == env and cached_token['expires'] > time.time():
                logger.debug(f"Token is authenticated in cache of {self.__class__.__name__}.")
                self.stats['authenticated_tokens_from_cache'] += 1
                return True
        except TypeError:
            pass

        # If token was in cache but expired, remove it from cache.
        self.api_tokens_cache.pop(api_token, None)

        return False


    @staticmethod
    def get_request_data(event):
        request_data_str = event.get('body', None)
        request_data = None
        if request_data_str:
            try:
                request_data = json.loads(request_data_str)
            except:
                logging.exception(f"Failed json.loads of request body: {request_data_str}")
                raise RequestValidationException("Request data must be a valid JSON")
        return request_data


    @staticmethod
    def strip_req_path(full_path):
        # Remove query string parameters and /
        path = full_path.split('?')[0]
        path = path.rstrip('/')
        return path


    @staticmethod
    @logging_wrapper(logging.INFO)
    def get_status_code(data):
        if data is None or isinstance(data, list) or isinstance(data, dict) and 'Error' not in data.keys():
            return 200
        elif isinstance(data, (str, dict)):
            data_str = str(data)
            if "bad request" in data_str.lower():
                return 400
            if "not found" in data_str.lower():
                return 404
            elif "fail" in data_str.lower():
                return 500
            elif "successfully created" in data_str.lower():
                return 201
            elif 'error' in data_str.lower() and isinstance(data, dict) and 'Error' in data.keys():
                return 500
            else:
                return 200
        else:
            logger.error(f"Unsupported format of `data`: {type(data)}. {data}")
            return 415


    def get_router(self):
        raise NotImplementedError
