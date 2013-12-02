# -*- encoding: utf-8 -*-

from datetime import datetime

TYPE_STRING = 'str'
TYPE_BOOLEAN = 'bool'
TYPE_INTEGER = 'int'
TYPE_NUMBER = 'num'
TYPE_DATE = 'date'
TYPE_TIME = 'dtm'

"""
Define mappings as functions, which can be passed the data format to make them conditional.

Lists begin with '[L' and finish with ';', for example '[Ljava.lang.Integer;'
"""

JAVA_MAPPING = {
                'java.lang.String': lambda x: TYPE_STRING,
                'java.lang.Boolean': lambda x: TYPE_BOOLEAN,
                'java.lang.Number': lambda x: TYPE_NUMBER,
                'java.util.Date': lambda x: TYPE_DATE if x and not('H' in x) else TYPE_TIME,
                'java.sql.Date': lambda x: TYPE_DATE if x and not('H' in x) else TYPE_TIME,
                'java.sql.Time': lambda x: TYPE_TIME,
                'java.sql.Timestamp': lambda x: TYPE_TIME,
                'java.lang.Double': lambda x: TYPE_NUMBER,
                'java.lang.Float': lambda x: TYPE_NUMBER,
                'java.lang.Integer': lambda x: TYPE_INTEGER,
                'java.lang.Long': lambda x: TYPE_INTEGER,
                'java.lang.Short': lambda x: TYPE_INTEGER,
                'java.math.BigInteger': lambda x: TYPE_INTEGER,
                'java.math.BigDecimal': lambda x: TYPE_NUMBER,
                }

MAX_PARAMS = 50  # Do not make this bigger than 999

PARAM_XXX_STRING_VALUE = 'param_%03i_string_value'
PARAM_XXX_BOOLEAN_VALUE = 'param_%03i_boolean_value'
PARAM_XXX_INTEGER_VALUE = 'param_%03i_integer_value'
PARAM_XXX_NUMBER_VALUE = 'param_%03i_number_value'
PARAM_XXX_DATE_VALUE = 'param_%03i_date_value'
PARAM_XXX_TIME_VALUE = 'param_%03i_time_value'

PARAM_VALUES = {
                TYPE_STRING: {
                              'value': PARAM_XXX_STRING_VALUE,
                              'if_false': '',
                              'py_types': (str, unicode)},
                TYPE_BOOLEAN: {
                               'value': PARAM_XXX_BOOLEAN_VALUE,
                               'if_false': False,
                               'py_types': (bool,)},
                TYPE_INTEGER: {
                               'value': PARAM_XXX_INTEGER_VALUE,
                               'if_false': 0,
                               'py_types': (int, long)},
                TYPE_NUMBER: {
                              'value': PARAM_XXX_NUMBER_VALUE,
                              'if_false': 0.0,
                              'py_types': (float,),
                              'convert': lambda x: float(x)},
                TYPE_DATE: {
                            'value': PARAM_XXX_DATE_VALUE,
                            'if_false': '',
                            'py_types': (str, unicode),
                            'convert': lambda x: datetime.strptime(x, '%Y-%m-%d'),
                            'conv_default': lambda x: datetime.strptime(x.value, '%Y%m%dT%H:%M:%S').strftime('%Y-%m-%d')},
                TYPE_TIME: {
                            'value': PARAM_XXX_TIME_VALUE,
                            'if_false': '',
                            'py_types': (str, unicode),
                            'convert': lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                            'conv_default': lambda x: datetime.strptime(x.value, '%Y%m%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')},
                }


# functions here will be passed a dictionary to evaluate reserved values. The dictionary should have:
#    'ids' - object ids in force
#    'uid' - the applicable user
#    'context' - the applicable context

RESERVED_PARAMS = {
                   'ids': lambda s, cr, uid, d: d.get('ids',[]),
                   'user_id': lambda s, cr, uid, d: d.get('uid', 0),
                   'user_name': lambda s, cr, uid, d: d.get('uid') and s.pool.get('res.users').browse(cr, uid, d['uid'], context=d.get('context')).name or '',
                   'context_lang': lambda s, cr, uid, d: d.get('context', {}).get('lang', ''),
                   'context_tz': lambda s, cr, uid, d: d.get('context', {}).get('tz', ''),
                   }


def check_java_list(type):
    if type[0:2] == '[L':
        return True, type[2:-1]
    return False, type
