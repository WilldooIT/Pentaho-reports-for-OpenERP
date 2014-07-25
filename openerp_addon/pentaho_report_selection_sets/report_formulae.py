# -*- encoding: utf-8 -*-

from datetime import date, datetime, timedelta
from dateutil import parser
import pytz
import json

from openerp import models, fields, _
from openerp.exceptions import except_orm
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

from openerp.addons.pentaho_reports.java_oe import *

from report_formulae_definitions import *

PARAM_XXX_FORMULA = 'param_%03i_formula'

FORMULA_OPERATORS = '+-*/'
QUOTES = "'" + '"'
DIGITS = '1234567890'
PAIRS = {'"': '"',
         "'": "'",
         '(': ')',
         }

VALUE_CONSTANT = 'constant'
VALUE_VARIABLE = 'variable'
VALUE_UNKNOWN = 'unknown'


def parameter_resolve_formula_column_name(parameters, index):
    return PARAM_XXX_FORMULA % index

def find_type_display_name(type):
    for ft in FUNCTION_TYPES:
        if ft[0] == type:
            return ft[1]
    return 'Unknown'

def search_string_to_next(s, searching, pointer):
    in_something = False
    in_depth = 0
    while pointer < len(s):
        pointer += 1
        if in_something:
            if s[pointer-1:pointer] == PAIRS[in_something]:
                in_depth -= 1
                if in_depth <= 0:
                    in_something = False
            elif s[pointer-1:pointer] == in_something:
                in_depth += 1
        else:
            if s[pointer-1:pointer] in searching:
                return s[:pointer-1]
            if s[pointer-1:pointer] in PAIRS:
                in_something = s[pointer-1:pointer]
                in_depth = 1
    return s

def discard_firstchar(s):
    return s[1:].strip()

def variable_ignore_case(known_variables, key):
    for x in known_variables.iterkeys():
        if x.lower() == key.lower():
            return x, known_variables[x]
    return None, {}

def establish_type(s, known_variables):
    """
        Checks a value and returns:
            Whether it is a CONSTANT or VARIABLE
            The Data Type of value
            The List Type of value (True for x2m)
            The True variable name
    """
    if len(s) >= 2 and s[:1] in QUOTES and s[-1:] == s[:1]:
        return VALUE_CONSTANT, TYPE_STRING, False, None
    if len(s) > 0 and s[:1] in (DIGITS + '-'):
        try:
            i = int(s)
            return VALUE_CONSTANT, TYPE_INTEGER, False, None
        except ValueError:
            pass
        try:
            f = float(s)
            return VALUE_CONSTANT, TYPE_NUMBER, False, None
        except ValueError:
            pass
    true_name, variable = variable_ignore_case(known_variables, s)
    return variable and VALUE_VARIABLE or VALUE_UNKNOWN, variable.get('type', None), variable.get('x2m', False), true_name

def retrieve_value(s, known_variables):
    if len(s) >= 2 and s[:1] in QUOTES and s[-1:] == s[:1]:
        return s[1:-1]
    if len(s) > 0 and s[:1] in (DIGITS + '-'):
        try:
            i = int(s)
            return i
        except ValueError:
            pass
        try:
            f = float(s)
            return f
        except ValueError:
            pass
    true_name, variable = variable_ignore_case(known_variables, s)
    result = json.loads(variable.get('calced_value', 'null'))
    if variable.get('type', None) == TYPE_DATE:
        result = datetime.strptime(result, DEFAULT_SERVER_DATE_FORMAT).date()
    if variable.get('type', None) == TYPE_TIME:
        result = datetime.strptime(result, DEFAULT_SERVER_DATETIME_FORMAT)
    return result


class selection_set_formula(models.Model):
    _name = 'ir.actions.report.set.formula'
    _description = 'Pentaho Report Selection Formulae'

    _columns = {
                }


    def check_formula_arguments(self, cr, uid, definition_args, passed_args, known_variables, function_name, context=None):

        def find_last_positional(definition_args):
            for x in range(len(definition_args), 0, -1):
                if not definition_args[x-1].get('name'):
                    return x-1
            return 0

        for index in range(0, len(definition_args)):
            if not definition_args[index].get('name'):
                if len(passed_args) < index+1 or passed_args[index][0]:
                    return _('Not enough positional arguments for formula "%s": %s required') % (function_name, find_last_positional(definition_args)+1)

        for index in range(0, len(passed_args)):
            if not passed_args[index][0]:
                if len(definition_args) < index+1 or definition_args[index].get('name'):
                    return _('Too many positional arguments for formula "%s": %s required') % (function_name, find_last_positional(definition_args)+1)
                compare_index = index
            else:
                for compare_index in range(0, len(definition_args)):
                    if definition_args[compare_index].get('name') == passed_args[index][0]:
                        break
                else:
                    return _('Unknown named argument for formula "%s": %s') % (function_name, passed_args[index][0])

            value_is_type, value_gives_type, value_gives_list, value_true_name = establish_type(passed_args[index][1], known_variables)
            if value_is_type == VALUE_UNKNOWN:
                return _('Argument value unknown for formula "%s": %s') % (function_name, passed_args[index][1])
            if not value_gives_type in definition_args[compare_index]['types']:
                return _('Argument type mismatch for formula "%s" %s: %s is %s') % (function_name, passed_args[index][0] and ('"%s"' % (passed_args[index][0],)) or ('argument %s' % (index+1,)), passed_args[index][1], find_type_display_name(value_gives_type))
            if not value_gives_list in definition_args[compare_index]['lists']:
                return _('Argument mismatch for formula "%s" %s: %s is %s') % (function_name, passed_args[index][0] and ('"%s"' % (passed_args[index][0],)) or ('argument %s' % (index+1,)), passed_args[index][1], value_gives_list and _('a list') or _('not a list'))
        return None

    def split_formula(self, cr, uid, formula_str, known_variables, context=None):
        """
        returns a list of operands.
        each operand is a dictionary:
            operator:        +-*/
            error:           string of one error in operand
            value:           an string with quotes, a number, or a variable
                             !!! undefined if it is a function
            returns:         type that this operand returns
            returns_2m:      True if operand returns a list
            function_name:
            function_args: list of tuples
                                (name or None, value)
                                where value is a quoted string, number, or variable
        """
        result = []

        operand = search_string_to_next(formula_str, FORMULA_OPERATORS, 1)
        formula_str = formula_str.replace(operand,'',1).strip()

        operand_dictionary = {'operator': operand[0:1],
                              'error': None,
                              }
        operand = discard_firstchar(operand)
        if operand:
            value_is_type, value_gives_type, value_gives_list, value_true_name = establish_type(operand, known_variables)
            if value_is_type != VALUE_UNKNOWN:
                operand_dictionary['value'] = value_true_name or operand
                operand_dictionary['returns'] = value_gives_type
                operand_dictionary['returns_2m'] = value_gives_list
            else:
                function_name = search_string_to_next(operand, '(', 0)
                operand = operand.replace(function_name,'',1).strip()

                if not operand:
                    operand_dictionary['value'] = function_name
                    operand_dictionary['returns'] = None
                    operand_dictionary['returns_2m'] = None
                else:
                    function_name = function_name.lower()
                    operand_dictionary['function_name'] = function_name
                    operand_dictionary['returns'] = FORMULAE.get(function_name,{}).get('type', None)
                    operand_dictionary['returns_2m'] = FORMULAE.get(function_name,{}).get('type_2m', None)
                    operand_dictionary['function_args'] = []
                    operand = discard_firstchar(operand)
                    while operand and operand[0:1] != ')':
                        if len(operand_dictionary['function_args']) > 0:
                            # don't strip first character for first parameter, after this, the first character is the ','
                            operand = discard_firstchar(operand)
                        function_param = search_string_to_next(operand, ',)', 0)
                        operand = operand.replace(function_param,'',1).strip()

                        param_split = search_string_to_next(function_param, '=', 0)
                        function_param = function_param.replace(param_split,'',1).strip()
                        if function_param:
                            function_param = discard_firstchar(function_param)
                            operand_dictionary['function_args'].append((param_split, function_param))
                        else:
                            operand_dictionary['function_args'].append((None, param_split.strip()))

                    if operand:
                        # remove ')'
                        operand = discard_firstchar(operand)
                        if operand:
                            operand_dictionary['error'] = _('Unable to interpret beyond formula "%s": %s') % (function_name, operand)
                    else:
                        operand_dictionary['error'] = _('Formula not closed: "%s"') % (function_name,)

                    if not operand_dictionary.get('error'):
                        if function_name.lower() in FORMULAE:
                            operand_dictionary['error'] = self.check_formula_arguments(cr, uid, FORMULAE[function_name]['arguments'], operand_dictionary['function_args'], known_variables, function_name, context=context)
                        else:
                            operand_dictionary['error'] = _('Formula undefined or restricted: "%s"') % (function_name,)

        if not operand_dictionary.get('returns') and not operand_dictionary.get('error'):
            operand_dictionary['error'] = _('Operand unknown or badly formed: %s') % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),)

        result.append(operand_dictionary)
        if formula_str:
            result.extend(self.split_formula(cr, uid, formula_str, known_variables, context=context))

        return result

    def operand_type_check(self, cr, uid, operand_dictionary, valid_operators, valid_types, valid_types_2m, eval_to_type, context=None):
        if not operand_dictionary['error']:
            if not operand_dictionary['returns'] in valid_types:
                operand_dictionary['error'] = _('Operand "%s", type "%s", not permitted for parameter of type "%s".') % (operand_dictionary.get('value') or operand_dictionary.get('function_name'), find_type_display_name(operand_dictionary['returns']), find_type_display_name(eval_to_type))
            elif not (operand_dictionary.get('returns_2m') or False) in valid_types_2m:
                operand_dictionary['error'] = _('Operand "%s", "%s list", not permitted for parameter of type "%s".') % (operand_dictionary.get('value') or operand_dictionary.get('function_name'), (operand_dictionary.get('returns_2m') and 'is' or 'not a') , find_type_display_name(eval_to_type))
            elif not operand_dictionary['operator'] in valid_operators:
                operand_dictionary['error'] = _('Operator "%s", at operand "%s", not permitted for parameter of type "%s".') % (operand_dictionary['operator'], operand_dictionary.get('value') or operand_dictionary.get('function_name'), find_type_display_name(eval_to_type))

    def eval_operand(self, cr, uid, operand_dictionary, known_variables, context=None):

        if operand_dictionary.get('value'):
            return operand_dictionary['operator'], operand_dictionary['returns'], operand_dictionary['returns_2m'], retrieve_value(operand_dictionary['value'], known_variables)

        formula_definition = FORMULAE[operand_dictionary['function_name']]
        replacements = dict.fromkeys([arg['insert_at'] for arg in formula_definition['arguments']], '')
        variables = {}

        for index in range(0, len(operand_dictionary['function_args'])):
            passed_arg = operand_dictionary['function_args'][index]
            if not passed_arg[0]:
                definition_arg = formula_definition['arguments'][index]
            else:
                for definition_arg in formula_definition['arguments']:
                    if definition_arg.get('name') == passed_arg[0]:
                        break
                else:
                    # should NEVER get here as it should have already validated arguments match
                    raise except_orm(_('Error'), _('Unexpected argument error.'))

            variables[index] = retrieve_value(passed_arg[1], known_variables)
            value = 'variables[%s]' % (index,)
            replacement_so_far = False

            if definition_arg.get('insert_as') or definition_arg.get('name'):
                value = '%s=%s' % (definition_arg.get('insert_as') or definition_arg.get('name'), value)
                replacement_so_far = replacements[definition_arg['insert_at']]

            replacements[definition_arg['insert_at']] = '%s%s' % (replacement_so_far and '%s, ' % (replacement_so_far,) or '', value)

        eval_string = formula_definition['call']
        for r_key in replacements:
            eval_string = eval_string.replace('%%%s' % (r_key, ), replacements[r_key])

        return operand_dictionary['operator'], operand_dictionary['returns'], operand_dictionary['returns_2m'], eval(eval_string)

    def check_string_formula(self, cr, uid, expected_type, operands, context=None):
        # every operator must be a '+'
        # every standard operand type can be accepted as they will be converted to strings, and appended...
        for operand_dictionary in operands:
            self.operand_type_check(cr, uid, operand_dictionary, '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME), (False, True), expected_type, context=context)

    def eval_string_formula(self, cr, uid, expected_type, operands, known_variables, context=None):
        def to_string(value, op_type, op_2m):
            if op_2m:
                return json.dumps(value)
            return op_type in (TYPE_STRING) and value or str(value)

        result_string = ''
        for operand_dictionary in operands:
            op_op, op_type, op_2m, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_string += to_string(op_result, op_type, op_2m)
        return result_string

    def check_boolean_formula(self, cr, uid, expected_type, operands, context=None):
        # only 1 operand allowed
        # must be a '+'
        # every standard operand type can be accepted as they will be converted to booleans using standard Python boolean rules
        self.operand_type_check(cr, uid, operands[0], '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME), (False,), expected_type, context=context)
        for operand_dictionary in operands[1:]:
            operand_dictionary['error'] = _('Excess operands not permitted for for this type of parameter: %s') % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),)

    def eval_boolean_formula(self, cr, uid, expected_type, operands, known_variables, context=None):
        def to_boolean(value, op_type, op_2m):
            return op_type in (TYPE_BOOLEAN) and value or bool(value)

        op_op, op_type, op_2m, op_result = self.eval_operand(cr, uid, operands[0], known_variables, context=context)
        result_bool += to_boolean(op_result, op_type, op_2m)
        return result_bool

    def check_numeric_formula(self, cr, uid, expected_type, operands, context=None):
        # every operator type is fine
        # only integers and numerics can be accepted
        for operand_dictionary in operands:
            self.operand_type_check(cr, uid, operand_dictionary, '+-*/', (TYPE_INTEGER, TYPE_NUMBER), (False,), expected_type, context=context)

    def eval_numeric_formula(self, cr, uid, expected_type, operands, known_variables, context=None):
        # all operands have been validated as integers or numbers already, so this is redundant.
        def to_number(value, op_type, op_2m):
            return op_type in (TYPE_INTEGER, TYPE_NUMBER) and value or float(value)

        result_num = 0.0
        for operand_dictionary in operands:
            op_op, op_type, op_2m, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_num = eval('result_num %s to_number(op_result, op_type, op_2m)' % (op_op,))
        return expected_type == TYPE_INTEGER and int(result_num) or result_num

    def check_date_formula(self, cr, uid, expected_type, operands, context=None):
        # first operand must be a date or datetime and a '+' operator
        self.operand_type_check(cr, uid, operands[0], '+', (TYPE_DATE, TYPE_TIME), (False,), expected_type, context=context)
        # others must be all time_deltas
        for operand_dictionary in operands[1:]:
            self.operand_type_check(cr, uid, operand_dictionary, '+-', (FTYPE_TIMEDELTA,), (False,), expected_type, context=context)

    def eval_date_formula(self, cr, uid, expected_type, operands, known_variables, context=None):
        # all operands have been validated as correct type, so these are redundant - if it errors, then we have a coding problem in the formula checks...
        def to_date(value, op_type, op_2m):
            return op_type in (TYPE_DATE, TYPE_TIME) and value or datetime.now()
        def to_timedelta(value, op_type, op_2m):
            return op_type in (FTYPE_TIMEDELTA) and value or timedelta()

        op_op, op_type, op_2m, op_result = self.eval_operand(cr, uid, operands[0], known_variables, context=context)
        result_dtm = op_result
        result_dtm_type = op_type
        for operand_dictionary in operands[1:]:
            op_op, op_type, op_2m, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_dtm = eval('result_dtm %s to_timedelta(op_result, op_type, op_2m)' % (op_op,))
        # OpenERP will assume datetimes are UTC, but here they are local!
        if result_dtm_type == TYPE_TIME:
            result_dtm = result_dtm.astimezone(pytz.timezone('UTC'))
        elif expected_type == TYPE_TIME:
            if context and context.get('tz'):
                result_dtm = pytz.timezone(context['tz']).localize(datetime.combine(result_dtm,datetime.min.time()), is_dst=False).astimezone(pytz.timezone('UTC'))
        return expected_type == TYPE_DATE and result_dtm.strftime(DEFAULT_SERVER_DATE_FORMAT) or result_dtm.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def validate_formula(self, cr, uid, formula_str, expected_type, expected_2m, known_variables, context=None):
        """
        returns a dictionary
            error:            string of one error in formula
            operands:         list of operand dictionaries
                              for list type variables, operands returned as a list of lists...
            dependent_values: list of variables needed for this formula to calculate
        """

        result = {'error': False}
        formula_str = formula_str.strip()

        if formula_str:
            if formula_str[0:1] == '=':
                formula_str = discard_firstchar(formula_str)

            # for lists:
            if expected_2m:
                if formula_str[:1] in '[(' and '[('.find(formula_str[:1]) == '])'.find(formula_str[-1:]):
                    formula_str = formula_str[1:-1].strip()
                    result['operands'] = []
                    result['dependent_values'] = []
                    while formula_str:
                        one_list_value = search_string_to_next(formula_str, ',', 0)
                        formula_str = formula_str.replace(one_list_value,'',1).strip()
                        one_list_formula = self.validate_formula(cr, uid, one_list_value, expected_type, False, known_variables, context=context)
                        result['error'] = result['error'] or one_list_formula['error']
                        if not one_list_formula.get('operands'):
                            if not result['error']:
                                result['error'] = _('Empty list value not permitted.')
                        else:
                            result['operands'].append(one_list_formula['operands'])
                        if one_list_formula.get('dependent_values'):
                            result['dependent_values'] = list(set(result['dependent_values']).union(set(one_list_formula['dependent_values'])))
                        if formula_str:
                            formula_str = discard_firstchar(formula_str)
                else:
                    result['error'] = _('List formulae must be enclosed in [] or ().')
                return result

            if not formula_str or not formula_str[0:1] in FORMULA_OPERATORS:
                formula_str = '+' + formula_str

            operands = self.split_formula(cr, uid, formula_str, known_variables, context=context)
            result['operands'] = operands

            if expected_type == TYPE_STRING:
                self.check_string_formula(cr, uid, expected_type, operands, context=context)
            if expected_type == TYPE_BOOLEAN:
                self.check_boolean_formula(cr, uid, expected_type, operands, context=context)
            if expected_type in (TYPE_INTEGER, TYPE_NUMBER):
                self.check_numeric_formula(cr, uid, expected_type, operands, context=context)
            if expected_type in (TYPE_DATE, TYPE_TIME):
                self.check_date_formula(cr, uid, expected_type, operands, context=context)

            for operand in operands:
                if operand['error']:
                    result['error'] = operand['error']
                    break

            else:
                dependent_values = set()
                for operand_dictionary in operands:
                    if operand_dictionary.get('value'):
                        value_is_type, value_gives_type, value_gives_list, value_true_name = establish_type(operand_dictionary['value'], known_variables)
                        if value_is_type == VALUE_VARIABLE:
                            dependent_values.add(value_true_name)
                    for function_arg in operand_dictionary.get('function_args',[]):
                        value_is_type, value_gives_type, value_gives_list, value_true_name = establish_type(function_arg[1], known_variables)
                        if value_is_type == VALUE_VARIABLE:
                            dependent_values.add(value_true_name)
                result['dependent_values'] = list(dependent_values)

        return result

    def evaluate_formula(self, cr, uid, formula_dict, expected_type, expected_2m, known_variables, context=None):
        result = None

        # for x2m results, operands is a list of lists
        if expected_2m:
            result = []
            for one_set_operands in formula_dict['operands']:
                single_value_dict = formula_dict.copy()
                single_value_dict['operands'] = one_set_operands
                result.append(self.evaluate_formula(cr, uid, single_value_dict, expected_type, False, known_variables, context=context))
            return result

        if expected_type == TYPE_STRING:
            result = self.eval_string_formula(cr, uid, expected_type, formula_dict['operands'], known_variables, context=context)
        if expected_type == TYPE_BOOLEAN:
            result = self.eval_boolean_formula(cr, uid, expected_type, formula_dict['operands'], known_variables, context=context)
        if expected_type in (TYPE_INTEGER, TYPE_NUMBER):
            result = self.eval_numeric_formula(cr, uid, expected_type, formula_dict['operands'], known_variables, context=context)
        if expected_type in (TYPE_DATE, TYPE_TIME):
            result = self.eval_date_formula(cr, uid, expected_type, formula_dict['operands'], known_variables, context=context)
        return result

    def localise(self, cr, uid, value, context=None):
        if context and context.get('tz'):
            value = pytz.timezone('UTC').localize(value, is_dst=False).astimezone(pytz.timezone(context['tz']))
        return value
