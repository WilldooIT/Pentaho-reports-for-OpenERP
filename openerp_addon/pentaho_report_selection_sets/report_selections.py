# -*- encoding: utf-8 -*-

from datetime import date, datetime
from dateutil import parser
import pytz
import json

from lxml import etree

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.java_oe import *
from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES

from report_formulae import *


class selection_set_header(orm.Model):
    _name = 'ir.actions.report.set.header'
    _description = 'Pentaho Report Selection Set Header'

    _columns = {
                'name': fields.char('Selection Set Description', size=64),
                'report_action_id': fields.many2one('ir.actions.report.xml', 'Report Name', readonly=True),
                'output_type': fields.selection(VALID_OUTPUT_TYPES, 'Report format', help='Choose the format for the output'),
                'parameters_dictionary': fields.text('parameter dictionary'), # Not needed, but helpful if we build a parameter set master view...
                'detail_ids': fields.one2many('ir.actions.report.set.detail', 'header_id', 'Selection Details'),
                'def_user_ids': fields.many2many('res.users', 'ir_actions_report_set_def_user_rel', 'header_id', 'user_id', 'Users (Default)'),
                'def_group_ids': fields.many2many('res.groups', 'ir_actions_report_set_def_group_rel', 'header_id', 'group_id', 'Groups (Default)'),
                }

    def selections_to_dictionary(self, cr, uid, id, parameters, x2m_unique_id, context=None):
        detail_obj = self.pool.get('ir.actions.report.set.detail')
        formula_obj = self.pool.get('ir.actions.report.set.formula')

        selections_to_load = self.browse(cr, uid, id, context=context)
        result = {'output_type': selections_to_load.output_type}

        arbitrary_force_calc = None
        known_variables = {}
        for index in range(0, len(parameters)):
            known_variables[parameters[index]['variable']] = {'type': parameters[index]['type'],
                                                              'x2m': parameter_can_2m(parameters, index),
                                                              'calculated': False,
                                                              }

        while True:
            any_calculated_this_time = False
            still_needed_dependent_values = []
            for index in range(0, len(parameters)):
                if not known_variables[parameters[index]['variable']]['calculated']:
                    for detail in selections_to_load.detail_ids:
                        if detail.variable == parameters[index]['variable']:
                            expected_type = parameters[index]['type']
                            expected_2m = parameter_can_2m(parameters, index)
                            # check expected_type as TYPE_DATE / TYPE_TIME, etc... and validate display_value is compatible with it

                            calculate_formula_this_time = False
                            use_value_this_time = True

                            if detail.calc_formula:
                                formula = formula_obj.validate_formula(cr, uid, detail.calc_formula, expected_type, expected_2m, known_variables, context=context)
                                #
                                # if there is an error, we want to ignore the formula and use standard processing of the value...
                                # if we are arbitrarily forcing a value, then also use standard processing of the value...
                                # if no error, then try to evaluate the formula
                                if formula['error'] or detail.variable == arbitrary_force_calc:
                                    pass
                                else:
                                    calculate_formula_this_time = True
                                    for dv in formula['dependent_values']:
                                        if not known_variables[dv]['calculated']:
                                            calculate_formula_this_time = False
                                            use_value_this_time = False
                                            still_needed_dependent_values.append(dv)

                            if calculate_formula_this_time or use_value_this_time:
                                if calculate_formula_this_time:
                                    display_value = json.dumps(formula_obj.evaluate_formula(cr, uid, formula, expected_type, expected_2m, known_variables, context=context))
                                else:
                                    display_value = detail.display_value
                                result[parameter_resolve_column_name(parameters, index)] = detail_obj.display_value_to_wizard(cr, uid, display_value, parameters, index, x2m_unique_id, context=context) 
                                result[parameter_resolve_formula_column_name(parameters, index)] = detail.calc_formula

                                known_variables[parameters[index]['variable']].update({'calculated': True,
                                                                                       'calced_value': detail_obj.wizard_value_to_display(cr, uid,
                                                                                                                                          result[parameter_resolve_column_name(parameters, index)],
                                                                                                                                          parameters, index, context=context),
                                                                                       })
                                any_calculated_this_time = True
                            break

            # if there are no outstanding calculations, then break
            if not still_needed_dependent_values:
                break

            # if some were calculated, and there are outstanding calculations, then loop again
            # if none were calculated, then force a calculation to break potential deadlocks of dependent values
            if any_calculated_this_time:
                arbitrary_force_calc = None
            else:
                arbitrary_force_calc = still_needed_dependent_values[0]
        return result


class selection_set_detail(orm.Model):
    _name = 'ir.actions.report.set.detail'
    _description = 'Pentaho Report Selection Set Detail'

    _columns = {'header_id': fields.many2one('ir.actions.report.set.header', 'Selection Set', ondelete='cascade', readonly=True),
                'variable': fields.char('Variable Name', size=64, readonly=True),
                'label': fields.char('Label', size=64, readonly=True),
                'counter': fields.integer('Parameter Number', readonly=True),
                'type': fields.selection(OPENERP_DATA_TYPES, 'Data Type', readonly=True),
                'x2m': fields.boolean('Data List Type'),
                'display_value': fields.text('Value'),
                'calc_formula': fields.char('Formula'),
                }

    _order = 'counter'

    def wizard_value_to_display(self, cr, uid, wizard_value, parameters_dictionary, index, context=None):
        result = self.pool.get('ir.actions.report.promptwizard').decode_wizard_value(cr, uid, parameters_dictionary, index, wizard_value, context=context)
        result = json.dumps(result)
        return result

    def display_value_to_wizard(self, cr, uid, selection_value, parameters_dictionary, index, x2m_unique_id, context=None):
        result = selection_value and json.loads(selection_value) or False
        result = self.pool.get('ir.actions.report.promptwizard').encode_wizard_value(cr, uid, parameters_dictionary, index, x2m_unique_id, result, context=context)
        return result


class report_prompt_with_selection_set(orm.TransientModel):
    _inherit = 'ir.actions.report.promptwizard'

    _columns = {
                'has_selns': fields.boolean('Has Selection Sets...'),
                'selectionset_id': fields.many2one('ir.actions.report.set.header', 'Stored Selections', ondelete='set null'),
                }

    def __init__(self, pool, cr):
        """ Dynamically add columns."""

        super(report_prompt_with_selection_set, self).__init__(pool, cr)

        for counter in range(0, MAX_PARAMS):
            field_name = PARAM_XXX_FORMULA % counter
            self._columns[field_name] = fields.char('Formula')

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}

        set_header_obj = self.pool.get('ir.actions.report.set.header')

        result = super(report_prompt_with_selection_set, self).default_get(cr, uid, fields, context=context)
        set_header_ids = set_header_obj.search(cr, uid, [('report_action_id', '=', result['report_action_id'])], context=context)
        result['has_selns'] = len(set_header_ids) > 0

        parameters = json.loads(result.get('parameters_dictionary', []))
        for index in range(0, len(parameters)):
            result[parameter_resolve_formula_column_name(parameters, index)] = ''

        if context.get('populate_selectionset_id'):
            selectionset = set_header_obj.browse(cr, uid, context['populate_selectionset_id'], context=context)
            if selectionset.report_action_id.id != result['report_action_id']:
                raise orm.except_orm(_('Error'), _('Report selections do not match service name called.'))

            # set this and let onchange be triggered and initialise correct values
            result['selectionset_id'] = context.pop('populate_selectionset_id')
        else:
            default_selset_id = False
            for sel_set in set_header_obj.browse(cr, uid, set_header_ids, context=context):
                if uid in [u.id for u in sel_set.def_user_ids]:
                    default_selset_id = sel_set.id
                    break # This will break out of the main loop, which is correct - we have an explicit default
                for g in sel_set.def_group_ids:
                    if uid in [u.id for u in g.users]:
                        default_selset_id = sel_set.id
                        break # This will break out of the inner loop, which is correct - we want to repeat the outer loop in case there is an explicit overriding default

            if default_selset_id:
                result['selectionset_id'] = default_selset_id

        return result

    def fvg_add_one_parameter(self, cr, uid, result, selection_groups, parameters, index, first_parameter, context=None):

        def add_subelement(element, type, **kwargs):
            sf = etree.SubElement(element, type)
            for k, v in kwargs.iteritems():
                if v is not None:
                    sf.set(k, v)

        super(report_prompt_with_selection_set, self).fvg_add_one_parameter(cr, uid, result, selection_groups, parameters, index, first_parameter, context=context)

        field_name = parameter_resolve_formula_column_name(parameters, index)
        result['fields'][field_name] = {'selectable': self._columns[field_name].selectable,
                                        'type': self._columns[field_name]._type,
                                        'size': self._columns[field_name].size,
                                        'string': self._columns[field_name].string,
                                        'views': {}
                                        }

        for sel_group in selection_groups:
            add_subelement(sel_group,
                           'field',
                           name = field_name,
                           modifiers = '{"invisible": true}',
                           )

    def onchange_selectionset_id(self, cr, uid, ids, selectionset_id, parameters_dictionary, x2m_unique_id, context=None):
        result = {'value': {}}
        if selectionset_id:
            parameters = json.loads(parameters_dictionary)
            result['value'].update(self.pool.get('ir.actions.report.set.header').selections_to_dictionary(cr, uid, selectionset_id, parameters, x2m_unique_id, context=context))
        return result
