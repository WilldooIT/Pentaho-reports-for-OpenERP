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

from .java_oe import (JAVA_MAPPING,
                      check_java_list,
                      PARAM_VALUES,
                      RESERVED_PARAMS)

SERVICE_NAME_PREFIX = 'report.'
DEFAULT_OUTPUT_TYPE = 'pdf'


def get_proxy_args(cr, uid, prpt_content):
    """Return the arguments needed by Pentaho server proxy.

    @return: Tuple with:
        [0]: Has the url for the Pentaho server.
        [1]: Has dict with basic arguments to pass to Pentaho server. This
             includes the connection settings and report definition but does
             not include any report parameter values.
    """
    pool = pooler.get_pool(cr.dbname)

    current_user = pool.get('res.users').browse(cr, uid, uid)
    config_obj = pool.get('ir.config_parameter')

    proxy_url = config_obj.get_param(
        cr, uid, 'pentaho.server.url',
        default='http://localhost:8080/pentaho-reports-for-openerp')

    proxy_argument = {
        'prpt_file_content': xmlrpclib.Binary(prpt_content),
        'connection_settings': {
            'openerp': {
                'host': config["xmlrpc_interface"] or 'localhost',
                'port': str(config["xmlrpc_port"]),
                'db': cr.dbname,
                'login': current_user.login,
                'password': current_user.password,
            }
        },
    }

    postgresconfig_host = config_obj.get_param(
        cr, uid, 'pentaho.postgres.host', default='localhost')
    postgresconfig_port = config_obj.get_param(
        cr, uid, 'pentaho.postgres.port', default='5432')
    postgresconfig_login = config_obj.get_param(
        cr, uid, 'pentaho.postgres.login')
    postgresconfig_password = config_obj.get_param(
        cr, uid, 'pentaho.postgres.password')

    if postgresconfig_host and postgresconfig_port and \
    postgresconfig_login and postgresconfig_password:
        proxy_argument['connection_settings'].update({
            'postgres': {
                'host': postgresconfig_host,
                'port': postgresconfig_port,
                'db': cr.dbname,
                'login': postgresconfig_login,
                'password': postgresconfig_password,
            }
        })

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

    def setup_report(self):
        ids = self.pool.get('ir.actions.report.xml').search(
            self.cr, self.uid,
            [('report_name', '=', self.name[7:]),
                ('is_pentaho_report', '=', True)],
            context=self.context)
        if not ids:
            raise orm.except_orm(
                _('Error'),
                _("Report service name '%s' is not a Pentaho report.")
                % self.name[7:])
        data = self.pool.get('ir.actions.report.xml').read(
            self.cr, self.uid, ids[0],
            ["pentaho_report_output_type", "pentaho_file"])
        self.default_output_type = data["pentaho_report_output_type"] or \
        DEFAULT_OUTPUT_TYPE
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

        proxy_url, proxy_argument = get_proxy_args(
            self.cr, self.uid, self.prpt_content)
        proxy = xmlrpclib.ServerProxy(proxy_url)
        return proxy.report.getParameterInfo(proxy_argument)

    def execute_report(self):
        proxy_url, proxy_argument = get_proxy_args(
            self.cr, self.uid, self.prpt_content)
        proxy = xmlrpclib.ServerProxy(proxy_url)
        proxy_parameter_info = proxy.report.getParameterInfo(proxy_argument)

        output_type = self.data and self.data.get('output_type', False) or \
        self.default_output_type or DEFAULT_OUTPUT_TYPE

        proxy_argument.update({
            'output_type': output_type,
            'report_parameters': dict([(param_name, param_formula(self)) for (param_name, param_formula) in RESERVED_PARAMS.iteritems() if param_formula(self)]),
        })

        if self.data and self.data.get('variables', False):
            proxy_argument['report_parameters'].update(self.data['variables'])
            for parameter in proxy_parameter_info:
                if parameter['name'] in proxy_argument['report_parameters'].keys():
                    value_type = parameter['value_type']
                    java_list, value_type = check_java_list(value_type)
                    if not value_type == 'java.lang.Object' and PARAM_VALUES[JAVA_MAPPING[value_type](parameter['attributes'].get('data-format', False))].get('convert',False):
                        # convert from string types to correct types
                        # for reporter
                        proxy_argument['report_parameters'][parameter['name']] = PARAM_VALUES[JAVA_MAPPING[value_type](parameter['attributes'].get('data-format', False))]['convert'](proxy_argument['report_parameters'][parameter['name']])
                    # turn in to list
                    if java_list:
                        proxy_argument['report_parameters'][parameter['name']] = [proxy_argument['report_parameters'][parameter['name']]]

        rendered_report = proxy.report.execute(proxy_argument).data
        if len(rendered_report) == 0:
            raise orm.except_orm(
                _('Error'),
                _("Pentaho returned no data for the report '%s'. Check report definition and parameters.") % self.name[7:])

        return (rendered_report, output_type)


class PentahoReportOpenERPInterface(report.interface.report_int):

    def __init__(self, name):
        if name in netsvc.Service._services:
            del netsvc.Service._services[name]

        super(PentahoReportOpenERPInterface, self).__init__(name)

    def create(self, cr, uid, ids, data, context):
        name = self.name
        report_instance = Report(name, cr, uid, ids, data, context)
        return report_instance.execute()


def register_pentaho_report(report_name):
    if not report_name.startswith(SERVICE_NAME_PREFIX):
        name = "%s%s" % (SERVICE_NAME_PREFIX, report_name)
    else:
        name = report_name

    if name in netsvc.Service._services:
        if isinstance(
            netsvc.Service._services[name], PentahoReportOpenERPInterface):
            return
        del netsvc.Service._services[name]

    PentahoReportOpenERPInterface(name)


def fetch_report_parameters(cr, uid, report_name, context=None):
    """Return the parameters object for this report.

    Returns the parameters object as returned by the Pentaho
    server.

    @param report_name: The service name for the report.
    """
    if not report_name.startswith(SERVICE_NAME_PREFIX):
        name = "%s%s" % (SERVICE_NAME_PREFIX, report_name)
    else:
        name = report_name

    return Report(name, cr, uid, [1], {}, context).fetch_report_parameters()


class ir_actions_report_xml(orm.Model):
    """Following OpenERP's (messed up) naming convention"""
    _inherit = 'ir.actions.report.xml'

    def register_all(self, cr):
        cr.execute("""SELECT * FROM ir_act_report_xml
            WHERE is_pentaho_report = 'TRUE' ORDER BY id""")
        records = cr.dictfetchall()
        for record in records:
            register_pentaho_report(record["report_name"])

        return super(ir_actions_report_xml, self).register_all(cr)
