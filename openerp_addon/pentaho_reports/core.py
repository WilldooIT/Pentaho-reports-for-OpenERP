# -*- encoding: utf-8 -*-
# Todo:
#    multiple prpt files for one action - allows for alternate formats.

import xmlrpclib
import base64

from openerp import netsvc
from openerp import pooler
from openerp import report
from openerp.osv import orm
from openerp.tools import config
from openerp.tools.translate import _
import logging
import time
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

from .java_oe import JAVA_MAPPING, check_java_list, PARAM_VALUES, RESERVED_PARAMS

_logger = logging.getLogger(__name__)

SERVICE_NAME_PREFIX = 'report.'
DEFAULT_OUTPUT_TYPE = 'pdf'


def get_date_length(date_format=DEFAULT_SERVER_DATE_FORMAT):
    return len((datetime.now()).strftime(date_format))


class _format(object):

    def set_value(self, cr, uid, name, object, field, lang_obj):
        self.object = object
        self._field = field
        self.name = name
        self.lang_obj = lang_obj


class _float_format(float, _format):
    def __init__(self, value):
        super(_float_format, self).__init__()
        self.val = value or 0.0

    def __str__(self):
        digits = 2
        if hasattr(self, '_field') and getattr(self._field, 'digits', None):
            digits = self._field.digits[1]
        if hasattr(self, 'lang_obj'):
            return self.lang_obj.format('%.' + str(digits) + 'f', self.name, True)
        return str(self.val)


class _int_format(int, _format):
    def __init__(self, value):
        super(_int_format, self).__init__()
        self.val = value or 0

    def __str__(self):
        if hasattr(self, 'lang_obj'):
            return self.lang_obj.format('%.d', self.name, True)
        return str(self.val)


class _date_format(str, _format):
    def __init__(self, value):
        super(_date_format, self).__init__()
        self.val = value and str(value) or ''

    def __str__(self):
        if self.val:
            if getattr(self, 'name', None):
                date = datetime.strptime(self.name[:get_date_length()], DEFAULT_SERVER_DATE_FORMAT)
                return date.strftime(str(self.lang_obj.date_format))
        return self.val


class _dttime_format(str, _format):
    def __init__(self, value):
        super(_dttime_format, self).__init__()
        self.val = value and str(value) or ''

    def __str__(self):
        if self.val and getattr(self, 'name', None):
            return datetime.strptime(self.name, DEFAULT_SERVER_DATETIME_FORMAT)\
                   .strftime("%s %s" % (str(self.lang_obj.date_format),
                                      str(self.lang_obj.time_format)))
        return self.val


class browse_record_list(list):
    def __init__(self, lst, context):
        super(browse_record_list, self).__init__(lst)
        self.context = context

    def __getattr__(self, name):
        res = browse_record_list([getattr(x, name) for x in self], self.context)
        return res

    def __str__(self):
        return "browse_record_list(" + str(len(self)) + ")"

_fields_process = {
        'float': _float_format,
        'date': _date_format,
        'integer': _int_format,
        'datetime': _dttime_format
    }


def get_proxy_args(instance, cr, uid, prpt_content, context_vars={}):
    """Return the arguments needed by Pentaho server proxy.

    @return: Tuple with:
        [0]: Has the url for the Pentaho server.
        [1]: Has dict with basic arguments to pass to Pentaho server. This
             includes the connection settings and report definition, as well
             as reserved parameters evaluated according to values in
             the dictionary "context_vars".
    """
    pool = pooler.get_pool(cr.dbname)

    current_user = pool.get('res.users').browse(cr, uid, uid)
    config_obj = pool.get('ir.config_parameter')

    proxy_url = config_obj.get_param(cr, uid, 'pentaho.server.url', default='http://localhost:8080/pentaho-reports-for-openerp')

    xml_interface = config_obj.get_param(cr, uid, 'pentaho.openerp.xml.interface', default='').strip() or config['xmlrpc_interface'] or 'localhost'
    xml_port = config_obj.get_param(cr, uid, 'pentaho.openerp.xml.port', default='').strip() or str(config['xmlrpc_port'])

    proxy_argument = {
                      'prpt_file_content': xmlrpclib.Binary(prpt_content),
                      'connection_settings': {'openerp': {'host': xml_interface,
                                                          'port': xml_port,
                                                          'db': cr.dbname,
                                                          'login': current_user.login,
                                                          'password': current_user.password,
                                                          }},
                      'report_parameters': dict([(param_name, param_formula(instance, cr, uid, context_vars)) for (param_name, param_formula) in RESERVED_PARAMS.iteritems() if param_formula(instance, cr, uid, context_vars)]),
                      }

    postgresconfig_host = config_obj.get_param(cr, uid, 'pentaho.postgres.host', default='localhost')
    postgresconfig_port = config_obj.get_param(cr, uid, 'pentaho.postgres.port', default='5432')
    postgresconfig_login = config_obj.get_param(cr, uid, 'pentaho.postgres.login')
    postgresconfig_password = config_obj.get_param(cr, uid, 'pentaho.postgres.password')

    if postgresconfig_host and postgresconfig_port and postgresconfig_login and postgresconfig_password:
        proxy_argument['connection_settings'].update({'postgres': {'host': postgresconfig_host,
                                                                   'port': postgresconfig_port,
                                                                   'db': cr.dbname,
                                                                   'login': postgresconfig_login,
                                                                   'password': postgresconfig_password,
                                                                   }})

    return proxy_url, proxy_argument


class Report(object):
    def __init__(self, name, cr, uid, ids, data, context):
        self.name = name
        self.cr = cr
        self.uid = uid
        self.ids = ids
        self.data = data
        self.context = context or {}
        self.pool = pooler.get_pool(self.cr.dbname)
        self.prpt_content = None
        self.default_output_type = DEFAULT_OUTPUT_TYPE
        self.context_vars = {
                             'ids': self.ids,
                             'uid': self.uid,
                             'context': self.context,
                             }

    def setup_report(self):
        ids = self.pool.get('ir.actions.report.xml').search(self.cr, self.uid, [('report_name', '=', self.name[7:]), ('is_pentaho_report', '=', True)], context=self.context)
        if not ids:
            raise orm.except_orm(_('Error'), _("Report service name '%s' is not a Pentaho report.") % self.name[7:])
        data = self.pool.get('ir.actions.report.xml').read(self.cr, self.uid, ids[0], ['pentaho_report_output_type', 'pentaho_file'])
        self.default_output_type = data['pentaho_report_output_type'] or DEFAULT_OUTPUT_TYPE
        self.prpt_content = base64.decodestring(data["pentaho_file"])

    def execute(self):
        self.setup_report()
        # returns report and format
        return self.execute_report()

    def fetch_report_parameters(self):
        """Return the parameters object for this report.

        Returns the parameters object as returned by the Pentaho
        server.
        """
        self.setup_report()

        proxy_url, proxy_argument = get_proxy_args(self, self.cr, self.uid, self.prpt_content, self.context_vars)
        proxy = xmlrpclib.ServerProxy(proxy_url)
        return proxy.report.getParameterInfo(proxy_argument)

    def execute_report(self):
        proxy_url, proxy_argument = get_proxy_args(self, self.cr, self.uid, self.prpt_content, self.context_vars)
        proxy = xmlrpclib.ServerProxy(proxy_url)
        proxy_parameter_info = proxy.report.getParameterInfo(proxy_argument)

        output_type = self.data and self.data.get('output_type', False) or self.default_output_type or DEFAULT_OUTPUT_TYPE
        proxy_argument['output_type'] = output_type

        if self.data and self.data.get('variables', False):
            proxy_argument['report_parameters'].update(self.data['variables'])
            for parameter in proxy_parameter_info:
                if parameter['name'] in proxy_argument['report_parameters'].keys():
                    value_type = parameter['value_type']
                    java_list, value_type = check_java_list(value_type)
                    if not value_type == 'java.lang.Object' and PARAM_VALUES[JAVA_MAPPING[value_type](parameter['attributes'].get('data-format', False))].get('convert', False):
                        # convert from string types to correct types for reporter
                        proxy_argument['report_parameters'][parameter['name']] = PARAM_VALUES[JAVA_MAPPING[value_type](parameter['attributes'].get('data-format', False))]['convert'](proxy_argument['report_parameters'][parameter['name']])
                    # turn in to list
                    if java_list:
                        proxy_argument['report_parameters'][parameter['name']] = [proxy_argument['report_parameters'][parameter['name']]]

        rendered_report = proxy.report.execute(proxy_argument).data
        if len(rendered_report) == 0:
            raise orm.except_orm(_('Error'), _("Pentaho returned no data for the report '%s'. Check report definition and parameters.") % self.name[7:])

        return (rendered_report, output_type)


class PentahoReportOpenERPInterface(report.interface.report_int):
    def __init__(self, name):
        if name in netsvc.Service._services:
            del netsvc.Service._services[name]
        super(PentahoReportOpenERPInterface, self).__init__(name)

    def create(self, cr, uid, ids, data, context):
        name = self.name
        report_instance = Report(name, cr, uid, ids, data, context)

        pool = pooler.get_pool(cr.dbname)
        ir_pool = pool.get('ir.actions.report.xml')
        report_xml_ids = ir_pool.search(cr, uid,
                [('report_name', '=', name[7:])], context=context)

        rendered_report, output_type = report_instance.execute()
        if report_xml_ids:
            report_xml = ir_pool.browse(cr, uid, report_xml_ids[0], context=context)
            model = context.get('active_model')
            if report_xml.attachment and model:
                crtemp = pooler.get_db(cr.dbname).cursor()  # Creating new cursor to prevent TransactionRollbackError
                                                            # when creating attachments, concurrency update have place otherwise
                self.create_attachment(crtemp, uid, ids, report_xml.attachment, rendered_report, output_type, model, context=context)

                # TODO: Will remodel bellow functionality as its causes a lot of bugs, it returns previous filename
                # Error in report registration

                # service_name = check_report_name(report_name)
                # if check_report_name(report_name) != self.name:
                    # Changing report stored filename

                    # report_xml = ir_pool.browse(crtemp, uid, report_xml_ids[0], context=context)
                    # report_xml.write({'report_name': report_name})
                    # change_service_name(self.name, service_name)
                    # self.name = service_name

                crtemp.commit()  # It means attachment will be created even if error occurs
                crtemp.close()
        return rendered_report, output_type

    def getObjects(self, cr, uid, ids, model, context):
        pool = pooler.get_pool(cr.dbname)
        return pool.get(model).browse(cr, uid, ids, list_class=browse_record_list, context=context, fields_process=_fields_process)

    def create_attachment(self, cr, uid, ids, attachment, rendered_report, output_type, model, context):
        """Generates attachment when report is called and links to object it is called from
        Returns: True """
        objs = self.getObjects(cr, uid, ids, model, context)
        pool = pooler.get_pool(cr.dbname)
        attachment_pool = pool.get('ir.attachment')
        for obj in objs:
            attachment_ids = attachment_pool.search(cr, uid, [('res_id', '=', obj.id), ('res_model', '=', model)], context=context)
            aname = eval(attachment, {'object': obj, 'version': str(len(attachment_ids)), 'time': time.strftime('%Y-%m-%d')})
            if aname:
                try:
                    name = '%s%s' % (aname, '' if aname.endswith(output_type) else '.' + output_type)
                    # Remove the default_type entry from the context: this
                    # is for instance used on the account.account_invoices
                    # and is thus not intended for the ir.attachment type
                    # field.
                    ctx = dict(context)
                    ctx.pop('default_type', None)
                    attachment_pool.create(cr, uid, {
                        'name': name,
                        'datas': base64.encodestring(rendered_report),
                        'datas_fname': name,
                        'res_model': model,
                        'res_name': aname,
                        'res_id': obj.id,
                        }, context={}
                    )
                except Exception:
                    #TODO: should probably raise a proper osv_except instead, shouldn't we? see LP bug #325632
                    _logger.error('Could not create saved report attachment', exc_info=True)
        return True

def check_report_name(report_name):
    """Adds 'report.' prefix to report name if not present already
    Returns: full report name
    """
    if not report_name.startswith(SERVICE_NAME_PREFIX):
        name = "%s%s" % (SERVICE_NAME_PREFIX, report_name)
    else:
        name = report_name
    return name

def change_service_name(old_name, new_name):
    """Deletes service with old name and register
    one with new name.
    """
    if old_name in netsvc.Service._services:
        del netsvc.Service._services[old_name]
    PentahoReportOpenERPInterface(new_name)

def register_pentaho_report(report_name):
    name = check_report_name(report_name)
    if name in netsvc.Service._services:
        del netsvc.Service._services[name]
    PentahoReportOpenERPInterface(name)


def fetch_report_parameters(cr, uid, report_name, context=None):
    """Return the parameters object for this report.

    Returns the parameters object as returned by the Pentaho
    server.

    @param report_name: The service name for the report.
    """
    name = check_report_name(report_name)
    return Report(name, cr, uid, [1], {}, context).fetch_report_parameters()


#Following OpenERP's (messed up) naming convention
class ir_actions_report_xml(orm.Model):
    _inherit = 'ir.actions.report.xml'

    def register_all(self, cr):
        cr.execute("""SELECT * FROM ir_act_report_xml
                        WHERE is_pentaho_report = 'TRUE'
                        ORDER BY id
                    """)
        records = cr.dictfetchall()
        for record in records:
            register_pentaho_report(record['report_name'])

        return super(ir_actions_report_xml, self).register_all(cr)
