import io
import os
import xmlrpclib
import base64

from lxml import etree

from datetime import datetime

from osv import osv, fields


#---------------------------------------------------------------------------------------------------------------

TYPE_STRING = 'str'
TYPE_BOOLEAN = 'bool'
TYPE_INTEGER = 'int'
TYPE_NUMBER = 'num'
TYPE_DATE = 'date'
TYPE_TIME = 'dtm'


# define mappings as functions, which can be passed the data format to make them conditional...

JAVA_MAPPING = {'class java.lang.String' : lambda x: TYPE_STRING,
                'class java.lang.Boolean' : lambda x: TYPE_BOOLEAN,
                'class java.lang.Number' : lambda x: TYPE_NUMBER,
                'class java.util.Date' : lambda x: TYPE_DATE if x and not('HH' in x) else TYPE_TIME,
                'class java.sql.Date' : lambda x: TYPE_DATE if x and not('HH' in x) else TYPE_TIME,
                'class java.sql.Time' : lambda x: TYPE_TIME,
                'class java.sql.Timestamp' : lambda x: TYPE_TIME,
                'class java.lang.Double' : lambda x: TYPE_NUMBER,
#                'class java.lang.Float' : lambda x: TYPE_NUMBER,
                'class java.lang.Integer' : lambda x: TYPE_INTEGER,
#                'class java.lang.Long' : lambda x: TYPE_INTEGER,
#                'class java.lang.Short' : lambda x: TYPE_INTEGER,
#                'class java.math.BigInteger' : lambda x: TYPE_INTEGER,
#                'class java.math.BigDecimal' : lambda x: TYPE_NUMBER,
                }

MAX_PARAMS = 50  # Do not make this bigger than 999
PARAM_XXX_TYPE = 'param_%03i_type'
PARAM_XXX_REQ = 'param_%03i_req'

PARAM_XXX_STRING_VALUE = 'param_%03i_string_value'
PARAM_XXX_BOOLEAN_VALUE = 'param_%03i_boolean_value'
PARAM_XXX_INTEGER_VALUE = 'param_%03i_integer_value'
PARAM_XXX_NUMBER_VALUE = 'param_%03i_number_value'
PARAM_XXX_DATE_VALUE = 'param_%03i_date_value'
PARAM_XXX_TIME_VALUE = 'param_%03i_time_value'

PARAM_VALUES = {TYPE_STRING : {'value' : PARAM_XXX_STRING_VALUE, 'if_false' : ''},
                TYPE_BOOLEAN : {'value' : PARAM_XXX_BOOLEAN_VALUE, 'if_false' : False},
                TYPE_INTEGER : {'value' : PARAM_XXX_INTEGER_VALUE, 'if_false' : 0},
                TYPE_NUMBER : {'value' : PARAM_XXX_NUMBER_VALUE, 'if_false' : 0},
                TYPE_DATE : {'value' : PARAM_XXX_DATE_VALUE, 'if_false' : '', 'convert' : lambda x: datetime.strptime(x, '%Y-%m-%d'), 'conv_default' : lambda x: datetime.strptime(x.value, '%Y%m%dT%H:%M:%S').strftime('%Y-%m-%d')},
                TYPE_TIME : {'value' : PARAM_XXX_TIME_VALUE, 'if_false' : '', 'convert' : lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'), 'conv_default' : lambda x: datetime.strptime(x.value, '%Y%m%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')},
                }

XML_LABEL = '__option_label__'
XML_FOCUS_VAL = '__focus_val__'

#---------------------------------------------------------------------------------------------------------------


class report_prompt_class(osv.osv_memory):

    _name = "ir.actions.report.promptwizard"

    _columns = {
                'report_name': fields.char('Report Name', size=64, readonly=True),
                'output_type' : fields.selection([('pdf', 'Portable Document (pdf)'),('xls', 'Excel Spreadsheet (xls)'),('csv', 'Comma Separated Values (csv)'),\
                                                  ('rtf', 'Rich Text (rtf)'), ('html', 'HyperText (html)'), ('txt', 'Plain Text (txt)')],\
                                                  'Report format', help='Choose the format for the output', required=True),
                }




    def __init__(self, pool, cr):
        """ Dynamically add columns
        """

        super(report_prompt_class, self).__init__(pool, cr)

#        selections = [map(lambda x: (x(False), ''), set(JAVA_MAPPING.values()))]
        longest = reduce(lambda l, x: l and max(l,len(x(False))) or len(x(False)), JAVA_MAPPING.values(), 0)

        for counter in range(0, MAX_PARAMS):
            field_name = PARAM_XXX_TYPE % counter
            self._columns[field_name] = fields.char('Parameter Type', size=longest)

            field_name = PARAM_XXX_REQ % counter
            self._columns[field_name] = fields.boolean('Parameter Required')

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




    def _parse_one_report_parameter_default_formula(self, formula, type):

        result = False

        if type == TYPE_DATE:
            if formula == '=NOW()':
                result = datetime.date.today().strftime('%Y-%m-%d')

        if type == TYPE_TIME:
            if formula == '=NOW()':
                result = datetime.date.today().strftime('%Y-%m-%d %H:%M:%S')

        return result




    def _parse_one_report_parameter(self, parameter):
        if not parameter.get('value_type','') in JAVA_MAPPING:
            raise osv.except_osv(('Error'), ("Unhandled parameter type (%s)." % parameter.get('value_type','')))

        if not parameter.get('name', False):
            raise osv.except_osv(('Error'), ("Unnamed parameter encountered."))

        result = {'variable' : parameter['name'], 'label' : parameter['attributes'].get('label','')}

        result['type'] = JAVA_MAPPING[parameter['value_type']](parameter['attributes'].get('data-format', False))

        if parameter.get('default_value',False):
            if PARAM_VALUES[result['type']].get('conv_default', False):
                result['default'] = PARAM_VALUES[result['type']]['conv_default'](parameter['default_value'])
            else:
                result['default'] = parameter['default_value']

        elif parameter['attributes'].get('default-value-formula',False):
            value = self._parse_one_report_parameter_default_formula(parameter['attributes']['default-value-formula'], result['type'])
            if value:
                result['default'] = value

        if parameter.get('is_mandatory',False):
            result['mandatory'] = parameter['is_mandatory']

        return result




    def _parse_report_parameters(self, report_parameters):

        print report_parameters

        result = []
        for parameter in report_parameters:
            if not parameter.get('attributes',{}):
                raise osv.except_osv(('Error'), ("Parameter received with no attributes."))

            # skip hidden parameters ({'attributes': {'hidden': 'true'}})
            if parameter['attributes'].get('hidden','false') != 'true':
                result.append(self._parse_one_report_parameter(parameter))

        if len(result) > MAX_PARAMS + 1:
            raise osv.except_osv(('Error'), ("Too many report parameters (%d)." % len(self.parameters) + 1))

        print result

        return result




    def _setup_parameters(self, cr, uid, context=None):

        if context is None:
            context={}

        ir_actions_obj = self.pool.get('ir.actions.report.xml')

        report_ids = ir_actions_obj.search(cr, uid, [('report_name', '=', context.get('service_name',''))], context=context)
        if not report_ids:
            raise osv.except_osv(('Error'), ("Invalid report associated with menu item."))

        report_record = ir_actions_obj.browse(cr, uid, report_ids[0], context=context)

        addons_path = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

        report_path = os.path.join(addons_path, report_record.report_file)

        report_time = os.path.getmtime(report_path)

        if not self.paramfile or self.paramfile['report_id'] != report_ids[0] or self.paramfile['report_path'] != report_path or self.paramfile['report_time'] != report_time:
            with open(report_path, 'rb') as prpt_file:
                encoded_prpt_file = io.BytesIO()
                base64.encode(prpt_file, encoded_prpt_file)

                proxy = xmlrpclib.ServerProxy("http://localhost:8090")
                proxy_argument = {
                    "_prpt_file_content": encoded_prpt_file.getvalue(),
                }

                report_parameters = proxy.report.get_parameter_info(proxy_argument)

                self.parameters = self._parse_report_parameters(report_parameters)

            self.paramfile = {'report_id': report_ids[0], 'report_path': report_path, 'report_time': report_time}




    def default_get(self, cr, uid, fields, context=None):

        self._setup_parameters(cr, uid, context=context)

        defaults = super(report_prompt_class, self).default_get(cr, uid, fields, context=context)

        defaults.update({'report_name': self.pool.get('ir.actions.report.xml').browse(cr, uid, self.paramfile['report_id'], context=context).name,
                         'output_type' : 'pdf',
                         })

        for index in range (0, len(self.parameters)):
            defaults[PARAM_XXX_TYPE % index] = self.parameters[index]['type']
            defaults[PARAM_XXX_REQ % index] = self.parameters[index]['type'] in [TYPE_DATE, TYPE_TIME] or self.parameters[index].get('mandatory', False)

            if self.parameters[index].get('default', False):
                defaults[PARAM_VALUES[self.parameters[index]['type']]['value'] % index] = self.parameters[index]['default']

        return defaults




    def _process_arch_repeaters(self, arch):
#        any group with @attrs='repeater' will be repeated for every valid option
        doc = etree.fromstring(arch)

        parent_map = dict((c, p) for p in doc.getiterator() for c in p)

        repeat_elements = doc.xpath("//group[@string='repeater']")
        for one_element in repeat_elements:
#            find the group, and strip the start and end enclosing group statements...
            base_xml = etree.tostring(one_element).strip()[25:-8]
#            add one copy of the xml for every parameter, replacing the label, and all other variables
            new_xml = ''
            for index in range(0, len(self.parameters)):
                new_xml += base_xml.replace(XML_LABEL, '%s :' % self.parameters[index]['label']).replace('000', '%03i' % index).replace(XML_FOCUS_VAL, '1' if index==0 else '0')

#            encase in a new wrapper, and add the children back
            new_element = etree.fromstring('<dummyrepeater>' + new_xml + '</dummyrepeater>')
            new_element_children = new_element.getchildren()
            for child in reversed(new_element_children):
                one_element.addnext(child)

#        remove the unneeded groups
        repeat_elements = doc.xpath("//group[@string='repeater']")
        for one_element in repeat_elements:
#            doc.remove(one_element)
            parent_map[one_element].remove(one_element)

        return etree.tostring(doc)




    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):

        self._setup_parameters(cr, uid, context=context)

        result = super(report_prompt_class, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

#        param_000_.... should already be defined on the form, and requested - need to ensure it is duplicated for every valid parameter
        for index in range (1, len(self.parameters)):
            result['fields'][PARAM_XXX_TYPE % index] = dict(result['fields'][PARAM_XXX_TYPE % 0])
            result['fields'][PARAM_XXX_REQ % index] = dict(result['fields'][PARAM_XXX_REQ % 0])

            for param_value in PARAM_VALUES:
                result['fields'][PARAM_VALUES[param_value]['value'] % index] = dict(result['fields'][PARAM_VALUES[param_value]['value'] % 0])

#         default_focus='1'


        result['arch'] = self._process_arch_repeaters(result['arch'])

        return result




    def _set_report_variables(self, wizard):

        result = {}

        for index in range (0, len(self.parameters)):
            result[self.parameters[index]['variable']] = getattr(wizard, PARAM_VALUES[self.parameters[index]['type']]['value'] % index, False) or PARAM_VALUES[self.parameters[index]['type']]['if_false']

        return result




    def check_report(self, cr, uid, ids, context=None):

        self._setup_parameters(cr, uid, context=context)

        wizard = self.browse(cr, uid, ids[0], context=context)

        if context is None:
            context = {}
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')

        data['output_type'] = wizard.output_type

        data['variables'] = self._set_report_variables(wizard)

        # to rely on standard report action, update the action's output
        self.pool.get('ir.actions.report.xml').write(cr, uid, [self.paramfile['report_id']], {'pentaho_report_output_type' : wizard.output_type}, context=context)

        return self._print_report(cr, uid, ids, data, context=context)




    def _print_report(self, cr, uid, ids, data, context=None):

        if context is None:
            context = {}

        return {
            'type': 'ir.actions.report.xml',
            'report_name': context.get('service_name', ''),
            'datas': data,
    }


report_prompt_class()
