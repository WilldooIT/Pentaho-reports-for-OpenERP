# -*- encoding: utf-8 -*-

import xmlrpclib
import base64

from lxml import etree

from datetime import date, datetime
import pytz

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from ..java_oe import *
from ..core import get_proxy_args, DEFAULT_OUTPUT_TYPE


class report_prompt_class(orm.TransientModel):
    _name = 'ir.actions.report.promptwizard'
    _columns = {
                'report_name': fields.char('Report Name', size=64, readonly=True),
                'output_type': fields.selection(
                                                [('pdf', 'Portable Document (pdf)'),
                                                 ('xls', 'Excel Spreadsheet (xls)'),
                                                 ('csv', 'Comma Separated Values (csv)'),
                                                 ('rtf', 'Rich Text (rtf)'),
                                                 ('html', 'HyperText (html)'),
                                                 ('txt', 'Plain Text (txt)')],
                                                'Report format', help='Choose the format for the output', required=True),
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

        self.paramfile = False

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

        if len(result) > MAX_PARAMS + 1:
            raise orm.except_orm(_('Error'), _('Too many report parameters (%d).') % len(self.parameters) + 1)

        return result

    def _setup_parameters(self, cr, uid, context=None):

        if context is None:
            context = {}

        ir_actions_obj = self.pool.get('ir.actions.report.xml')

        report_ids = ir_actions_obj.search(cr, uid, [('report_name', '=', context.get('service_name', ''))], context=context)
        if not report_ids:
            raise orm.except_orm(_('Error'), _('Invalid report associated with menu item.'))

        report_record = ir_actions_obj.browse(cr, uid, report_ids[0], context=context)

        prpt_content = base64.decodestring(report_record.pentaho_file)

        if not self.paramfile or self.paramfile['report_id'] != report_ids[0] or self.paramfile['prpt_content'] != prpt_content or self.paramfile['context'] != context:

            proxy_url, proxy_argument = get_proxy_args(self, cr, uid, prpt_content, {
                                                                                     'ids': [],           # meaningless in this context, so pass nothing...
                                                                                     'uid': uid,
                                                                                     'context': context,
                                                                                     })
            proxy = xmlrpclib.ServerProxy(proxy_url)
            report_parameters = proxy.report.getParameterInfo(proxy_argument)

            self.parameters = self._parse_report_parameters(report_parameters, context=context)

            self.paramfile = {'report_id': report_ids[0],
                              'prpt_content': prpt_content,
                              'context': context
                              }

    def default_get(self, cr, uid, fields, context=None):

        self._setup_parameters(cr, uid, context=context)
        result = super(report_prompt_class, self).default_get(cr, uid, fields, context=context)

        result.update({'report_name': self.pool.get('ir.actions.report.xml').browse(cr, uid, self.paramfile['report_id'], context=context).name,
                       'output_type': self.pool.get('ir.actions.report.xml').browse(cr, uid, self.paramfile['report_id'], context=context).pentaho_report_output_type or DEFAULT_OUTPUT_TYPE,
                       })

        for index in range(0, len(self.parameters)):
            if self.parameters[index].get('default', False):
                result[PARAM_VALUES[self.parameters[index]['type']]['value'] % index] = self.parameters[index]['default']

        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        # fields_view_get() is called during module installation, in which case there is no
        # service_name in the context.
        if context.get('service_name', '').strip() == '':
            return super(report_prompt_class, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

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

        def add_subelement(element, type, **kwargs):
            sf = etree.SubElement(element, type)
            for k, v in kwargs.iteritems():
                sf.set(k, v)

        # this will force a reload of parameters and not use the
        # cached data - this is important as the available selections
        # may have changed...
        self.paramfile = None

        self._setup_parameters(cr, uid, context=context)

        result = super(report_prompt_class, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

        doc = etree.fromstring(result['arch'])

        selection_groups = doc.findall('.//group[@string="Selections"]')

        first_parameter = True

        for index in range(0, len(self.parameters)):
            add_field(result,
                      PARAM_VALUES[self.parameters[index]['type']]['value'] % index,
                      selection_options = self.parameters[index].get('selection_options', False),
                      required = self.parameters[index].get('mandatory', False)
                      )

            if not self.parameters[index].get('hidden', False):
                for sel_group in selection_groups:
                    if first_parameter:
                        add_subelement(sel_group,
                                       'separator',
                                       colspan = sel_group.get('col', '4'),
                                       string = 'Selections',
                        )

                    add_subelement(sel_group,
                                   'field',
                                   name = PARAM_VALUES[self.parameters[index]['type']]['value'] % index,
                                   string = self.parameters[index]['label'],
                                   default_focus = '1' if first_parameter else '0',
                                   modifiers = '{"required": %s}' % 'true' if self.parameters[index].get('mandatory', False) else 'false',
                                   )

                    first_parameter = False

        for sel_group in selection_groups:
            sel_group.set('string', '')

        result['arch'] = etree.tostring(doc)
        return result

    def _set_report_variables(self, wizard):

        result = {}
        for index in range(0, len(self.parameters)):
            result[self.parameters[index]['variable']] = getattr(wizard, PARAM_VALUES[self.parameters[index]['type']]['value'] % index, False) or PARAM_VALUES[self.parameters[index]['type']]['if_false']

        return result

    def check_report(self, cr, uid, ids, context=None):

        if context is None:
            context = {}

        self._setup_parameters(cr, uid, context=context)
        wizard = self.browse(cr, uid, ids[0], context=context)

        data = {
                'ids': context.get('active_ids', []),
                'model': context.get('active_model', 'ir.ui.menu'),
                'output_type': wizard.output_type,
                'variables': self._set_report_variables(wizard)
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
