# Todo:
#    alternate user may need to be passed if executing the report (if emailing) - concurrency errors
#    restructure xml parsing of repeating section
#    change to use the prpt file stored in the DB, not off disk (allows different DBs to have different prpt files)
#    ?? make ports configurable, especially for sql based reports - Need user profiles, perhaps
#    also for proxy connections
#    selection pulldowns
#    multiple prpt files for one action - allows for alternate formats.


import io
import os
import logging
import subprocess
import xmlrpclib

import netsvc
import pooler
import report
from osv import osv, fields

from datetime import datetime

from .wizard.report_prompt import JAVA_MAPPING, PARAM_VALUES

from tools import config


class Report(object):
    def __init__(self, name, cr, uid, ids, data, context):
        self.name = name
        self.cr = cr
        self.uid = uid
        self.ids = ids
        self.data = data
        self.context = context or {}
        self.pool = pooler.get_pool(self.cr.dbname)
        self.report_path = None
        self.output_format = "pdf"

    def execute(self):
        self.logger = logging.getLogger()

        ids = self.pool.get("ir.actions.report.xml").search(self.cr, self.uid, [("report_name", "=", self.name[7:]), ("report_rml", "ilike", ".prpt")], context = self.context)
        data = self.pool.get("ir.actions.report.xml").read(self.cr, self.uid, ids[0], ["report_rml", "pentaho_report_output_type"])
        self.report_path = data["report_rml"]
        self.output_format = data["pentaho_report_output_type"] or "pdf"
        self.report_path = os.path.join(self.get_addons_path(), self.report_path)

        self.logger.debug("self.ids: %s" % self.ids)
        self.logger.debug("self.data: %s" % self.data)
        self.logger.debug("self.context: %s" % self.context)
        self.logger.info("Requested report: '%s'" % self.report_path)

        return (self.execute_report(), self.output_format)
    
    def get_addons_path(self):
        return os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

    def execute_report(self):
        user_model = self.pool.get("res.users")
        current_user = user_model.browse(self.cr, self.uid, self.uid)

        with open(self.report_path, "rb") as prpt_file:
            prpt_file_content = xmlrpclib.Binary(prpt_file.read())

            #TODO: Make this configurable from inside the UI - In report_prompt wizard, too...
            proxy = xmlrpclib.ServerProxy("http://localhost:8090")
            proxy_argument = {
                "_prpt_file_content": prpt_file_content,
                "_output_type": self.output_format,
                "_openerp_host": config["xmlrpc_interface"] or "localhost", "_openerp_port": str(config["xmlrpc_port"]), 
                "_openerp_db": self.cr.dbname,
                "_openerp_login": current_user.login, "_openerp_password": current_user.password,
                "ids": self.ids
            }

#            postgresconfig_obj = self.pool.get('pentaho.postgres.config')
#            postgresconfig_ids = postgresconfig_obj.search(self.cr, self.uid, [], context=context)
#            if postgresconfig_ids:
#                postgresconfig = postgresconfig_obj.browse(self.cr, self.uid, postgresconfig_ids[0], context=context)
#                proxy_argument.update({'_postgres_host': postgresconfig.host or 'localhost',
#                                       '_postgres_port': postgresconfig.port or '5432',
#                                       '_postgres_db': self.cr.dbname,
#                                       '_postgres_login': postgresconfig.login,
#                                       '_postgres_password': postgresconfig.password,
#                                       })

            postgresconfig_host = self.pool.get('ir.config_parameter').get_param(self.cr, self.uid, 'postgres.host', default='localhost')
            postgresconfig_port = self.pool.get('ir.config_parameter').get_param(self.cr, self.uid, 'postgres.port', default='5432')
            postgresconfig_login = self.pool.get('ir.config_parameter').get_param(self.cr, self.uid, 'postgres.login')
            postgresconfig_password = self.pool.get('ir.config_parameter').get_param(self.cr, self.uid, 'postgres.password')

            if postgresconfig_host and postgresconfig_port and postgresconfig_login and postgresconfig_password:
                proxy_argument.update({'_postgres_host': postgresconfig_host,
                                       '_postgres_port': postgresconfig_port,
                                       '_postgres_db': self.cr.dbname,
                                       '_postgres_login': postgresconfig_login,
                                       '_postgres_password': postgresconfig_password,
                                       })

            proxy_parameter_info = proxy.report.getParameterInfo(proxy_argument)

            if self.data and self.data.get('variables', False):
                for variable in self.data['variables']:
                    proxy_argument[variable] = self.data['variables'][variable]

                for parameter in proxy_parameter_info:
                    if parameter['name'] in proxy_argument.keys():
                        if PARAM_VALUES[JAVA_MAPPING[parameter['value_type']](parameter['attributes'].get('data-format', False))].get('convert',False):
                            # convert from string types to correct types for reporter
                            proxy_argument[parameter['name']] = PARAM_VALUES[JAVA_MAPPING[parameter['value_type']](parameter['attributes'].get('data-format', False))]['convert'](proxy_argument[parameter['name']])

            if self.data and self.data.get('output_type', False):
                proxy_argument['_output_type']=self.data['output_type']

            rendered_report = proxy.report.execute(proxy_argument).data

        return rendered_report

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
    name = "report.%s" % report_name

    if name in netsvc.Service._services:
        if isinstance(netsvc.Service._services[name], PentahoReportOpenERPInterface):
            return
        del netsvc.Service._services[name]
    
    PentahoReportOpenERPInterface(name)

#Following OpenERP's (messed up) naming convention
class ir_actions_report_xml(osv.osv):
    _inherit = "ir.actions.report.xml"

    def register_all(self, cr):
        cr.execute("SELECT * FROM ir_act_report_xml WHERE report_rml ILIKE '%.prpt' ORDER BY id")
        records = cr.dictfetchall()
        for record in records:
            register_pentaho_report(record["report_name"])

        return super(ir_actions_report_xml, self).register_all(cr)

ir_actions_report_xml()
