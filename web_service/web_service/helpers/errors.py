'''Custom exceptions for error handling in views.py'''
import logging

class GenericException(Exception):
    '''Raise a non-specific exception with a given code and message'''
    http_codes = dict()
    # HTTP 4xx -- client-side error
    http_codes[400] = {'type':'Bad Request',
                       'message':'Missing one or more required parameters, please re-try'}
    http_codes[401] = {'type': 'Bad Request',
                       'message': 'User has exceeded workspace limit'}
    http_codes[406] = {'type':'Bad Request',
                       'message':'Invalid value for one or more parameters, please re-try'}
    # HTTP 5xx -- server-side error
    http_codes[500] = {'type':'Server Error',
                       'message':'Server has encountered an error'}

    '''Log error message and return an Exception'''
    def __init__(self, code, error=None, error_type=None):
        Exception.__init__(self)
        logging.error(GenericException.http_codes[code]['message'])
        self.status_code = code
        if error:
            self.error = error
            logging.error(error)
        if error_type:
            self.error_type = error_type

    def to_dict(self):
        '''convert response to dict'''
        resp = dict(GenericException.http_codes[self.status_code])
        if 'error' in dir(self):
            resp['error'] = self.error
        if 'error_type' in dir(self):
            resp['error_type'] = self.error_type
        resp['status_code'] = self.status_code
        return resp

# TODO: create child classes from GenericException -
# -- DatabaseException, ApplicationException, Request or ClientRequestException
