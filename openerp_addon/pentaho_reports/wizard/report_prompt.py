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
TYPE_NUMBER = 'num'
TYPE_DATE = 'date'
TYPE_TIME = 'time'
MAPPING = {'class java.lang.String' : TYPE_STRING,
           'class java.lang.Boolean' : TYPE_BOOLEAN,
           'class java.lang.Number' : TYPE_NUMBER,
           'class java.util.Date' : TYPE_DATE,
           }

MAX_PARAMS = 50  # Do not make this bigger than 999
PARAM_XXX_TYPE = 'param_%03i_type'
PARAM_XXX_STRING_VALUE = 'param_%03i_string_value'
PARAM_XXX_BOOLEAN_VALUE = 'param_%03i_boolean_value'
PARAM_XXX_NUMBER_VALUE = 'param_%03i_number_value'
PARAM_XXX_DATE_VALUE = 'param_%03i_date_value'
PARAM_XXX_TIME_VALUE = 'param_%03i_time_value'

XML_LABEL = '__option_label__'
XML_FOCUS_VAL = '__focus_val__'

DATE_FORMAT_MAPPINGS = {'d': '%d', 'dd': '%d',                                  #day
                        'M': '%m', 'MM': '%m', 'MMM': '%b', 'MMMM': '%B',       #month
                        'yy' : '%y', 'yyyy': '%Y',                              #year
                        'E': '%a', 'EE': '%a', 'EEE': '%a', 'EEEE': '%A',       #dow
                        'D': '%j', 'DD': '%j', 'DDD': '%j',                     #day in year
                        'w': '%W',                                              #week in year
                        }
TIME_FORMAT_MAPPINGS = {'H': '%H', 'HH': '%H',                                  #hour 24
                        'h': '%I', 'hh': '%I',                                  #hour 12
                        'm': '%M', 'mm': '%M',                                  #min
                        's': '%S', 'ss': '%S',                                  #sec
                        'a': '%p', 'aa': '%p',                                  #am/pm
                        'z': '%z', 'zz': '%z', 'zzz': '%z', 'zzzz': '%Z',       #timezone
                        }

#---------------------------------------------------------------------------------------------------------------


class report_prompt_class(osv.osv_memory):

    _name = "ir.actions.report.promptwizard"

    _columns = {
                'report_name': fields.char('Report Name', size=64, readonly=True),
                'output_type' : fields.selection([('pdf', 'Portable Document (pdf)'),('xls', 'Excel Spreadsheet (xls)'),('csv', 'Comma Separated Values (csv)'),\
                                                  ('rtf', 'Rich Text (rtf)'), ('html', 'HyperText (html)'), ('txt', 'Plain Text (txt)')],\
                                                  'Report format', help='Choose the format for the output', required=True),

#                'param_000_type' : fields.selection([map(lambda x: (x, x), set(MAPPING.values()))],''),
#                'param_000_string_value' : fields.char('', size=64),

                }




    def __init__(self, pool, cr):
        """ Dynamically add columns
        """

        super(report_prompt_class, self).__init__(pool, cr)

#        selections = [map(lambda x: (x, x), set(MAPPING.values()))]
        longest = reduce(lambda l, x: l and max(l,len(x)) or len(x), MAPPING.values(), 0)

        for counter in range(0, MAX_PARAMS):
            field_name = PARAM_XXX_TYPE % counter
            self._columns[field_name] = fields.char('Parameter Type', size=longest)

            field_name = PARAM_XXX_STRING_VALUE % counter
            self._columns[field_name] = fields.char('String Value', size=64)

            field_name = PARAM_XXX_BOOLEAN_VALUE % counter
            self._columns[field_name] = fields.boolean('Boolean Value')

            field_name = PARAM_XXX_NUMBER_VALUE % counter
            self._columns[field_name] = fields.float('Number Value')

            field_name = PARAM_XXX_DATE_VALUE % counter
            self._columns[field_name] = fields.date('Date Value')

            field_name = PARAM_XXX_TIME_VALUE % counter
            self._columns[field_name] = fields.datetime('Time Value')

        self.parameters = False




    def _parse_one_report_parameter_default_formula(self, formula, type):

        result = False

        if type == TYPE_DATE:
            if formula == '=NOW()':
                result = datetime.date.today().strftime('%Y-%m-%d')

        if type == TYPE_TIME:
            if formula == '=NOW()':
                result = datetime.date.today().strftime('%Y-%m-%d %H:%M:%S')

        return result




    def _check_format(self, mappings, length, check_string):

        if check_string[0:length] in mappings:
            result = (mappings[check_string[0:length]], check_string[length:])
        elif length>1:
            result = self._check_format(mappings, length-1, check_string)
        else:
            result = (check_string[0:1], check_string[1:])

        return result




    def _parse_one_report_parameter_data_format(self, check_string, type):

        result = False

        if type == TYPE_DATE:
            result = ''
            while check_string:
                next, check_string = self._check_format(DATE_FORMAT_MAPPINGS, 4, check_string)
                result += next

        if type == TYPE_TIME:
            result = ''
            while check_string:
                next, check_string = self._check_format(dict(DATE_FORMAT_MAPPINGS.items() + TIME_FORMAT_MAPPINGS.items()), 4, check_string)
                result += next

        return result




    def _parse_one_report_parameter(self, parameter):
        if not parameter.get('value_type','') in MAPPING:
            raise osv.except_osv(('Error'), ("Unhandled parameter type (%s)." % parameter.get('value_type','')))

        if not parameter.get('name', False):
            raise osv.except_osv(('Error'), ("Unnamed parameter encountered."))

        result = {'variable' : parameter['name'], 'label' : parameter['attributes'].get('label','')}

        result['type'] = MAPPING[parameter['value_type']]

        if parameter['attributes'].get('default-value-formula',False):
            formula = self._parse_one_report_parameter_default_formula(parameter['attributes']['default-value-formula'], result['type'])
            if formula:
                result['default'] = formula

        if parameter['attributes'].get('data-format',False):
            format = self._parse_one_report_parameter_data_format(parameter['attributes']['data-format'], result['type'])
            if format:
                result['format'] = format

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

        if not self.parameters:
            ir_actions_obj = self.pool.get('ir.actions.report.xml')
            user_obj = self.pool.get("res.users")

            report_ids = ir_actions_obj.search(cr, uid, [('report_name', '=', context.get('service_name',''))], context=context)
            if not report_ids:
                raise osv.except_osv(('Error'), ("Invalid report associated with menu item."))

            self.report_id = report_ids[0]
            report_record = ir_actions_obj.browse(cr, uid, report_ids[0], context=context)

            addons_path = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

            report_path = os.path.join(addons_path, report_record.report_file)

            with open(report_path, 'rb') as prpt_file:
                encoded_prpt_file = io.BytesIO()
                base64.encode(prpt_file, encoded_prpt_file)

                proxy = xmlrpclib.ServerProxy("http://localhost:8090")
                proxy_argument = {
                    "_prpt_file_content": encoded_prpt_file.getvalue(),
                }

                report_parameters = proxy.report.get_parameter_info(proxy_argument)

                self.parameters = self._parse_report_parameters(report_parameters)




    def default_get(self, cr, uid, fields, context=None):

        self._setup_parameters(cr, uid, context=context)

        defaults = super(report_prompt_class, self).default_get(cr, uid, fields, context=context)

        defaults.update({'report_name': self.pool.get('ir.actions.report.xml').browse(cr, uid, self.report_id, context=context).name,
                         'output_type' : 'pdf',
                         })

        for index in range (0, len(self.parameters)):
            defaults[PARAM_XXX_TYPE % index] = self.parameters[index]['type']

            if self.parameters[index].get('default', False):
                if self.parameters[index]['type'] == TYPE_STRING:
                    defaults[PARAM_XXX_STRING_VALUE % index] = self.parameters[index]['default']
                if self.parameters[index]['type'] == TYPE_BOOLEAN:
                    defaults[PARAM_XXX_BOOLEAN_VALUE % index] = self.parameters[index]['default']
                if self.parameters[index]['type'] == TYPE_NUMBER:
                    defaults[PARAM_XXX_NUMBER_VALUE % index] = self.parameters[index]['default']
                if self.parameters[index]['type'] == TYPE_DATE:
                    defaults[PARAM_XXX_DATE_VALUE % index] = self.parameters[index]['default']
                if self.parameters[index]['type'] == TYPE_TIME:
                    defaults[PARAM_XXX_TIME_VALUE % index] = self.parameters[index]['default']

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
            result['fields'][PARAM_XXX_STRING_VALUE % index] = dict(result['fields'][PARAM_XXX_STRING_VALUE % 0])
            result['fields'][PARAM_XXX_BOOLEAN_VALUE % index] = dict(result['fields'][PARAM_XXX_BOOLEAN_VALUE % 0])
            result['fields'][PARAM_XXX_NUMBER_VALUE % index] = dict(result['fields'][PARAM_XXX_NUMBER_VALUE % 0])
            result['fields'][PARAM_XXX_DATE_VALUE % index] = dict(result['fields'][PARAM_XXX_DATE_VALUE % 0])
            result['fields'][PARAM_XXX_TIME_VALUE % index] = dict(result['fields'][PARAM_XXX_TIME_VALUE % 0])

#         default_focus='1'


        result['arch'] = self._process_arch_repeaters(result['arch'])

        return result




    def _set_report_variables(self, wizard):

        result = {}

        for index in range (0, len(self.parameters)):
            if self.parameters[index]['type'] == TYPE_STRING:
                value= getattr(wizard,PARAM_XXX_STRING_VALUE % index,'') or ''
            elif self.parameters[index]['type'] == TYPE_BOOLEAN:
                value= getattr(wizard,PARAM_XXX_BOOLEAN_VALUE % index,False) or False
            elif self.parameters[index]['type'] == TYPE_NUMBER:
                value= getattr(wizard,PARAM_XXX_NUMBER_VALUE % index,False) or 0
            elif self.parameters[index]['type'] == TYPE_DATE:
                value= getattr(wizard,PARAM_XXX_DATE_VALUE % index,False) or ''
                if self.parameters[index].get('format', False) and value:
                    value= datetime.strptime(value, '%Y-%m-%d').strftime(self.parameters[index]['format'])
            elif self.parameters[index]['type'] == TYPE_TIME:
                value= getattr(wizard,PARAM_XXX_TIME_VALUE % index,False) or ''
                if self.parameters[index].get('format', False) and value:
                    value= datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime(self.parameters[index]['format'])
            else:
                value= ''

            result[self.parameters[index]['variable']] = value

        return result




    def check_report(self, cr, uid, ids, context=None):

        wizard = self.browse(cr, uid, ids[0], context=context)

        if context is None:
            context = {}
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')

        data['output_type'] = wizard.output_type

        data['variables'] = self._set_report_variables(wizard)

        import pdb
        pdb.set_trace()

        # to rely on standard report action, update the action's output
        self.pool.get('ir.actions.report.xml').write(cr, uid, [self.report_id], {'pentaho_report_output_type' : wizard.output_type}, context=context)

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
