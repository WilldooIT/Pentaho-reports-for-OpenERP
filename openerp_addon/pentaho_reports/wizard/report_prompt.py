# -*- encoding: utf-8 -*-

import xmlrpclib
import base64
import json

from lxml import etree

from datetime import date, datetime
import pytz

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from ..java_oe import *
from ..core import get_proxy_args, VALID_OUTPUT_TYPES, DEFAULT_OUTPUT_TYPE


class report_prompt_class(orm.TransientModel):
    _name = 'ir.actions.report.promptwizard'

    def _multi_select_values(self, cr, uid, ids, field_name, args, context=None):
        mpwiz_obj = self.pool.get('ir.actions.report.multivalues.promptwizard')
        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            mpw_ids = mpwiz_obj.search(cr, uid, [('x2m_unique_id', '=', wiz.x2m_unique_id), ('entry_num', '=', args['entry_num']), ('selected', '=', True)], context=context)
            res[wiz.id] = mpw_ids
        return res

    def _multi_select_values_store(self, cr, uid, id, field_name, value, args, context=None):
        wiz = self.browse(cr, uid, id, context=context)
        mpwiz_obj = self.pool.get('ir.actions.report.multivalues.promptwizard')
        mpw_ids = mpwiz_obj.search(cr, uid, [('x2m_unique_id', '=', wiz.x2m_unique_id), ('entry_num', '=', args['entry_num'])], context=context)
        mpwiz_obj.write(cr, uid, mpw_ids, {'selected': False}, context=context)
        if type(value) in (list, tuple):
            if type(value[0]) in (list, tuple) and len(value[0]) == 3 and value[0][0] == 6:
                mpwiz_obj.write(cr, uid, value[0][2], {'selected': True})
        return True

    _columns = {
                'report_action_id': fields.many2one('ir.actions.report.xml', 'Report Name', readonly=True),
                'output_type': fields.selection(VALID_OUTPUT_TYPES, 'Report format', help='Choose the format for the output', required=True),
                'parameters_dictionary': fields.text('parameter dictionary'),
                'x2m_unique_id': fields.integer('2M Unique Id'),
                }

    def __init__(self, pool, cr):
        """ Dynamically add columns."""

        super(report_prompt_class, self).__init__(pool, cr)

        for counter in range(0, MAX_PARAMS):
            field_name = PARAM_XXX_STRING_VALUE % counter
            self._columns[field_name] = fields.char('String Value', size=64)
            field_name = PARAM_XXX_BOOLEAN_VALUE % counter
            self._columns[field_name] = fields.boolean('Boolean Value')
            field_name = PARAM_XXX_INTEGER_VALUE % counter
            self._columns[field_name] = fields.integer('Integer Value')
            field_name = PARAM_XXX_NUMBER_VALUE % counter
            self._columns[field_name] = fields.float('Number Value')
            field_name = PARAM_XXX_DATE_VALUE % counter
            self._columns[field_name] = fields.date('Date Value')
            field_name = PARAM_XXX_TIME_VALUE % counter
            self._columns[field_name] = fields.datetime('Time Value')
            field_name = PARAM_XXX_2M_VALUE % counter
            self._columns[field_name] = fields.function(self._multi_select_values.im_func,
                                                        arg={"entry_num": counter},
                                                        fnct_inv=self._multi_select_values_store.im_func,
                                                        fnct_inv_arg={"entry_num": counter},
                                                        method=False, type='many2many', relation='ir.actions.report.multivalues.promptwizard', string='Multi-Select')

    def _parse_one_report_parameter_default_formula(self, formula, type, context=None):
        """
        Previously, we were not getting a default value if the report had
        a default formula, so we endeavoured to generate a value.

        However, default formulae are now (correctly) being evaluated
        by the Pentaho server and are passed back as default values.
        So, we should never actually end up in here!

        The concept and code, however, remains valid and may be necessary
        in the future.
        """
        result = False

        if formula == '=NOW()':
            now = datetime.date.now()
            if context and context.get('tz'):
                now = pytz.timezone('UTC').localize(now, is_dst=False).astimezone(pytz.timezone(context['tz']))

            if type == TYPE_DATE:
                result = now.strftime(DEFAULT_SERVER_DATE_FORMAT)

            if type == TYPE_TIME:
                result = now.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        return result

    def _parse_one_report_parameter(self, parameter, context=None):
        """
        Hidden values should be set by default values or context.

        Creates a dictionary:

            'variable': variable_name,
            'label': label,
            'type': data type,

        Optional:
            'default': default value either from report or context
            'mandatory': True if field is required
            'selection_options' : [('val', 'name'), ('val', 'name')]
            'multi_select' : True if list of values allowed. However, we can not prompt for this, so it is pretty much ignored...
            'hidden' : True for non-displayed parameters
        """
        value_type = parameter.get('value_type', '')
        java_list, value_type = check_java_list(value_type)

        if not value_type in JAVA_MAPPING:
            raise orm.except_orm(_('Error'), _('Unhandled parameter type (%s).') % parameter.get('value_type', ''))

        if not parameter.get('name', False):
            raise orm.except_orm(_('Error'), _('Unnamed parameter encountered.'))

        result = {'variable': parameter['name'],
                  'label': parameter['attributes'].get('label', '')
                  }

        result['type'] = JAVA_MAPPING[value_type](parameter['attributes'].get('data-format', False))
        if java_list:
            result['multi_select'] = True

        if parameter['name'] in context.get('pentaho_defaults', {}).keys():
            result['default'] = context['pentaho_defaults'][parameter['name']]

        elif parameter.get('default_value', False):
            default_value = parameter['default_value']
            if type(default_value) in (list, tuple):
                default_value = default_value[0]

            if PARAM_VALUES[result['type']].get('conv_default', False):
                result['default'] = PARAM_VALUES[result['type']]['conv_default'](default_value)
            else:
                result['default'] = default_value

            # Default date or datetime is passed from Pentaho in local time without a timezone.
            # If it is a datetime value, we need to convert to UTC for OpenERP to handle it correctly.
            if result['type'] == TYPE_TIME:
                if context and context.get('tz'):
                    result['default'] = pytz.timezone(context['tz']).localize(datetime.strptime(result['default'], DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(pytz.timezone('UTC')).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        elif parameter['attributes'].get('default-value-formula', False):
            value = self._parse_one_report_parameter_default_formula(parameter['attributes']['default-value-formula'], result['type'], context=context)
            if value:
                result['default'] = value

        if parameter.get('is_mandatory', False):
            result['mandatory'] = parameter['is_mandatory']

        if result['type'] in (TYPE_DATE, TYPE_TIME):
            result['mandatory'] = True

        if parameter['attributes'].get('parameter-render-type', False) in ('dropdown', 'list', 'radio', 'checkbox', 'togglebutton'):
            result['selection_options'] = parameter.get('selection_options', [])

        if parameter['attributes'].get('hidden', 'false') == 'true':
            result['hidden'] = True

        return result

    def _parse_report_parameters(self, report_parameters, context=None):

        result = []
        for parameter in report_parameters:
            if not parameter.get('name') in RESERVED_PARAMS.keys():
                if not parameter.get('attributes',{}):
                    raise orm.except_orm(_('Error'), _('Parameter received with no attributes.'))

                result.append(self._parse_one_report_parameter(parameter, context=context))

        if len(result) > MAX_PARAMS:
            raise orm.except_orm(_('Error'), _('Too many report parameters (%d).') % len(result))

        return result

    def _find_report_id(self, cr, uid, context=None):
        report_ids = self.pool.get('ir.actions.report.xml').search(cr, uid, [('report_name', '=', context.get('service_name', ''))], context=context)
        if not report_ids:
            raise orm.except_orm(_('Error'), _('Invalid report associated with menu item.'))
        return report_ids[0]

    def _setup_parameters(self, cr, uid, report_id, context=None):
        if context is None:
            context = {}

        report_record = self.pool.get('ir.actions.report.xml').browse(cr, uid, report_id, context=context)

        prpt_content = base64.decodestring(report_record.pentaho_file)

        proxy_url, proxy_argument = get_proxy_args(self, cr, uid, prpt_content, {
                                                                                 'ids': [],           # meaningless in this context, so pass nothing...
                                                                                 'uid': uid,
                                                                                 'context': context,
                                                                                 })
        proxy = xmlrpclib.ServerProxy(proxy_url)
        report_parameters = proxy.report.getParameterInfo(proxy_argument)

        return self._parse_report_parameters(report_parameters, context=context)

    def report_defaults_dictionary(self, cr, uid, report_action_id, parameters, x2m_unique_id, context=None):
        report_action = self.pool.get('ir.actions.report.xml').browse(cr, uid, report_action_id, context=context)
        result = {'output_type': report_action.pentaho_report_output_type or DEFAULT_OUTPUT_TYPE}

        for index in range(0, len(parameters)):
            if parameters[index].get('default'):
                result[parameter_resolve_column_name(parameters, index)] = parameters[index]['default'] # TODO: Needs to be validated for list values - especially for M2M!

        mpwiz_obj = self.pool.get('ir.actions.report.multivalues.promptwizard')
        for index in range(0, len(parameters)):
            if parameter_can_2m(parameters, index):
                mpwiz_obj.write(cr, uid, mpwiz_obj.search(cr, uid, [('x2m_unique_id', '=', x2m_unique_id), ('entry_num', '=', index)], context=context), {'selected': False}, context=context)

        return result

    def create_x2m_entries(self, cr, uid, parameters, context=None):
        x2m_unique_id = False
        mpwiz_obj = self.pool.get('ir.actions.report.multivalues.promptwizard')
        for index in range(0, len(parameters)):
            if parameter_can_2m(parameters, index):
                if not x2m_unique_id:
                    mpwiz_ids = mpwiz_obj.search(cr, uid, [('x2m_unique_id', '>', 0)], order='x2m_unique_id desc', limit=1, context=context)
                    if mpwiz_ids:
                        x2m_unique_id = mpwiz_obj.browse(cr, uid, mpwiz_ids[0], context=context).x2m_unique_id + 1
                    else:
                        x2m_unique_id = 1

                selection_options = type(parameters[index].get('selection_options')) in (list, tuple) and parameters[index]['selection_options'] or []
                for item in selection_options:
                    mpwiz_obj.create(cr, uid, {'x2m_unique_id': x2m_unique_id, 'entry_num': index, 'selected': False,
                                               'sel_int': item[0] if parameters[index]['type'] == TYPE_INTEGER else False,
                                               'sel_str': item[0] if parameters[index]['type'] == TYPE_STRING else False,
                                               'sel_num': item[0] if parameters[index]['type'] == TYPE_NUMBER else False,
                                               'name': item[1],
                                               }, context=context)
        return x2m_unique_id

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context={}
        report_action_id = self._find_report_id(cr, uid, context=context)
        parameters = self._setup_parameters(cr, uid, report_action_id, context=context)

        result = super(report_prompt_class, self).default_get(cr, uid, fields, context=context)
        result.update({'report_action_id': report_action_id,
                       'parameters_dictionary': json.dumps(parameters),
                       })

        x2m_unique_id = self.create_x2m_entries(cr, uid, parameters, context=context)
        if x2m_unique_id:
            result['x2m_unique_id'] = x2m_unique_id

        result.update(self.report_defaults_dictionary(cr, uid, report_action_id, parameters, x2m_unique_id, context=context))
        return result

    def fvg_add_one_parameter(self, cr, uid, result, selection_groups, parameters, index, first_parameter, context=None):

        def add_field(result, field_name, selection_options=False, required=False):

            result['fields'][field_name] = {
                                            'selectable': self._columns[field_name].selectable,
                                            'type': self._columns[field_name]._type,
                                            'size': self._columns[field_name].size,
                                            'string': self._columns[field_name].string,
                                            'views': {}
                                            }

            if required:
                result['fields'][field_name]['required'] = required

            if type(selection_options) == list:
                result['fields'][field_name]['type'] = 'selection'
                result['fields'][field_name]['selection'] = selection_options

        def add_2m_field(result, field_name, selection_options=False, required=False):
            add_field(result, field_name, selection_options=False, required=required)

            result['fields'][field_name].update({
                                                 'relation': 'ir.actions.report.multivalues.promptwizard',
                                                 'function': 'self._multi_select_values',
                                                 'fnct_inv': 'self._multi_select_values_store',
                                                 'readonly': 0,
                                                 }
                                                )

        def add_subelement(element, type, **kwargs):
            sf = etree.SubElement(element, type)
            for k, v in kwargs.iteritems():
                if v is not None:
                    sf.set(k, v)

        field_name = parameter_resolve_column_name(parameters, index)
        is_2m = parameter_can_2m(parameters, index)
        if is_2m:
            add_2m_field(result,
                         field_name,
                         selection_options = parameters[index].get('selection_options', False),
                         required = parameters[index].get('mandatory', False),
                         )
        else:
            add_field(result,
                      field_name,
                      selection_options = parameters[index].get('selection_options', False),
                      required = parameters[index].get('mandatory', False),
                      )

        for sel_group in selection_groups:
            default_focus = '0'
            if not first_parameter and not parameters[index].get('hidden', False):
                add_subelement(sel_group,
                               'separator',
                               colspan = sel_group.get('col', '4'),
                               string = 'Selections',
                )

                first_parameter.update({'index': index,
                                        'name': field_name,
                                        })
                default_focus = '1'

            add_subelement(sel_group,
                           'field',
                           name = field_name,
                           string = parameters[index]['label'],
                           default_focus = default_focus,
                           modifiers = '{"required": %s, "invisible": %s}' % 
                                            ('true' if parameters[index].get('mandatory', False) else 'false',
                                             'true' if parameters[index].get('hidden', False) else 'false',
                                             ),
                           widget = is_2m and 'many2many_tags' or None,
                           domain = is_2m and ('[("x2m_unique_id", "=", x2m_unique_id), ("entry_num", "=", %d)]' % index) or None,
                           )

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        # fields_view_get() is called during module installation, in which case there is no
        # service_name in the context.
        if context.get('service_name', '').strip() == '':
            return super(report_prompt_class, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

        # reload parameters as selection pull down options can change
        report_action_id = self._find_report_id(cr, uid, context=context)
        parameters = self._setup_parameters(cr, uid, report_action_id, context=context)

        result = super(report_prompt_class, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

        doc = etree.fromstring(result['arch'])

        selection_groups = doc.findall('.//group[@string="Selections"]')

        first_parameter = {}

        for index in range(0, len(parameters)):
            self.fvg_add_one_parameter(cr, uid, result, selection_groups, parameters, index, first_parameter, context=context)

        for sel_group in selection_groups:
            sel_group.set('string', '')

        result['arch'] = etree.tostring(doc)
        return result

    def decode_wizard_value(self, cr, uid, parameters, index, value, enc_json=False, context=None):
        if parameter_can_2m(parameters, index):
            result = value and [(x.sel_int if parameters[index]['type'] == TYPE_INTEGER else \
                                 x.sel_str if parameters[index]['type'] == TYPE_STRING else \
                                 x.sel_num if parameters[index]['type'] == TYPE_NUMBER else \
                                 False) for x in value] \
                            or []
            if enc_json:
                result = json.dumps(result)
        else:
            result = value or PARAM_VALUES[parameters[index]['type']]['if_false']
        return result

    def encode_wizard_value(self, cr, uid, parameters, index, x2m_unique_id, value, enc_json=False, context=None):
        mpwiz_obj = self.pool.get('ir.actions.report.multivalues.promptwizard')

        if parameter_can_2m(parameters, index) and enc_json:
            result = json.loads(value)
        else:
            result = value

        if parameter_can_2m(parameters, index):
            if not type(result) in (list, tuple):
                result = []
            sel_ids = []
            for v in result:
                v_domain = ('sel_int', '=', v) if parameters[index]['type'] == TYPE_INTEGER else \
                           ('sel_str', '=', v) if parameters[index]['type'] == TYPE_STRING else \
                           ('sel_num', '=', v) if parameters[index]['type'] == TYPE_NUMBER else \
                           False
                if v_domain:
                    ids = mpwiz_obj.search(cr, uid, [('x2m_unique_id', '=', x2m_unique_id), ('entry_num', '=', index), v_domain], context=context)
                    if ids:
                        sel_ids.append(ids[0])
            result = [(6, 0, sel_ids)]
        return result

    def _set_report_variables(self, cr, uid, wizard, context=None):
        parameters = json.loads(wizard.parameters_dictionary)
        result = {}
        for index in range(0, len(parameters)):
            result[parameters[index]['variable']] = self.decode_wizard_value(cr, uid, parameters, index, getattr(wizard, parameter_resolve_column_name(parameters, index)), context=context)
        return result

    def check_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {
                'ids': context.get('active_ids', []),
                'model': context.get('active_model', 'ir.ui.menu'),
                'output_type': wizard.output_type,
                'variables': self._set_report_variables(cr, uid, wizard, context=context)
                }
        return self._print_report(cr, uid, ids, data, context=context)

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        return {
                'type': 'ir.actions.report.xml',
                'report_name': context.get('service_name', ''),
                'datas': data,
                }


class report_prompt_m2m(orm.TransientModel):
    _name = 'ir.actions.report.multivalues.promptwizard'
    _columns = {
                'x2m_unique_id': fields.integer('2M Unique Id'),
                'entry_num': fields.integer('Entry Num'),
                'selected': fields.boolean('Selected'),
                'sel_int': fields.integer('Selection Integer'),
                'sel_str': fields.char('Selection String'),
                'sel_num': fields.float('Selection Number'),
                'name': fields.char('Selection Value'),
                }
