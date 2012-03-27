import io
import os
import xmlrpclib
import base64

from osv import osv, fields


#---------------------------------------------------------------------------------------------------------------

TYPE_STRING = 'str'
MAPPING = {'class java.lang.String' : TYPE_STRING}

PARAM_XXX_TYPE = 'param_%03i_type'
PARAM_XXX_STRING_VALUE = 'param_%03i_string_value'

XML_OPTION_LABEL = '__option_label__'

#---------------------------------------------------------------------------------------------------------------


class Report_Prompt(osv.osv_memory):

    _name = "ir.actions.report.promptwizard"

    _columns = {
                'report_name': fields.char('Report Name', size=64, readonly=True),
                'output_type' : fields.selection([('pdf', 'Portable Document (pdf)'),('xls', 'Excel Spreadsheet (xls)'),('csv', 'Comma Separated Values (csv)'),\
                                                  ('rtf', 'Rich Text (rtf)'), ('html', 'HyperText (html)'), ('txt', 'Plain Text (txt)')],\
                                                  'Report format', help='Choose the format for the output', required=True),

                'param_000_type' : fields.selection([(TYPE_STRING,''),],''),
                'param_000_string_value' : fields.char('', size=64),

                }


    def __init__(self, cr, uid):
        super(Report_Prompt, self).__init__(cr, uid)
        self.parameters = False


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

                self.parameters = []
                for parameter in report_parameters:
                    if parameter.get('value_type','') in MAPPING and \
                            parameter.get('name','') and \
                            parameter.get('attributes',{}) and parameter['attributes'].get('hidden','false') != 'true':

                        one_param = {'variable' : parameter['name'], 'label' : parameter['attributes'].get('label','')}

                        one_param['type'] = MAPPING[parameter['value_type']]

                        one_param['default'] = 'a'

                        self.parameters.append(one_param)

                print self.parameters


    def default_get(self, cr, uid, fields, context=None):

        self._setup_parameters(cr, uid, context=context)

        result = {'report_name': self.pool.get('ir.actions.report.xml').browse(cr, uid, self.report_id, context=context).name,
                  'output_type' : 'pdf',
                  }

        for index in range (0, len(self.parameters)):
            result[PARAM_XXX_TYPE % index] = self.parameters[index]['type']

            if self.parameters[index].get('default', False):
                if self.parameters[index]['type'] == TYPE_STRING:
                    result[PARAM_XXX_STRING_VALUE % index] = self.parameters[index]['default']

        return result



    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):

        self._setup_parameters(cr, uid, context=context)

        result = super(Report_Prompt, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

        for index in range (0, len(self.parameters)):
            result['arch'] = result['arch'].replace(XML_OPTION_LABEL,'%s :' % self.parameters[index]['label'])

        return result



    def check_report(self, cr, uid, ids, context=None):

        wizard = self.browse(cr, uid, ids[0], context=context)

        if context is None:
            context = {}
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.uiwillow.menu')

        data['output_type'] = wizard.output_type

        data['variables'] = {}
        for index in range (0, len(self.parameters)):
            if self.parameters[index]['type'] == TYPE_STRING:
                value= getattr(wizard,PARAM_XXX_STRING_VALUE % index,'')
            else:
                value=''
            data['variables'][self.parameters[index]['variable']] = value

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


Report_Prompt()
