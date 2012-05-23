# Todo:
#    restructure xml parsing of repeating section
#    change to use the prpt file stored in the DB, not off disk (allows different DBs to have different prpt files)
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
        config_obj = self.pool.get('ir.config_parameter')
        current_user = user_model.browse(self.cr, self.uid, self.uid)

        with open(self.report_path, "rb") as prpt_file:
            prpt_file_content = xmlrpclib.Binary(prpt_file.read())

            proxy = xmlrpclib.ServerProxy(config_obj.get_param(self.cr, self.uid, 'pentaho.server.url', default='http://localhost:8090'))
            proxy_argument = {
                              "prpt_file_content": prpt_file_content,
                              "output_type": self.output_format,
                              "connection_settings" : {'openerp' : {"host": config["xmlrpc_interface"] or "localhost",
                                                                    "port": str(config["xmlrpc_port"]), 
                                                                    "db": self.cr.dbname,
                                                                    "login": current_user.login,
                                                                    "password": current_user.password,
                                                                    }},
                              "report_parameters" : {"ids": self.ids} if self.ids else {},
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

            postgresconfig_host = config_obj.get_param(self.cr, self.uid, 'postgres.host', default='localhost')
            postgresconfig_port = config_obj.get_param(self.cr, self.uid, 'postgres.port', default='5432')
            postgresconfig_login = config_obj.get_param(self.cr, self.uid, 'postgres.login')
            postgresconfig_password = config_obj.get_param(self.cr, self.uid, 'postgres.password')

            if postgresconfig_host and postgresconfig_port and postgresconfig_login and postgresconfig_password:
                proxy_argument['connection_settings'].update({'postgres' : {'host': postgresconfig_host,
                                                                            'port': postgresconfig_port,
                                                                            'db': self.cr.dbname,
                                                                            'login': postgresconfig_login,
                                                                            'password': postgresconfig_password,
                                                                            }})

            proxy_parameter_info = proxy.report.getParameterInfo(proxy_argument)

            if self.data and self.data.get('variables', False):

                proxy_argument['report_parameters'].update(self.data['variables'])

                for parameter in proxy_parameter_info:
                    if parameter['name'] in proxy_argument['report_parameters'].keys():
                        if PARAM_VALUES[JAVA_MAPPING[parameter['value_type']](parameter['attributes'].get('data-format', False))].get('convert',False):
                            # convert from string types to correct types for reporter
                            proxy_argument['report_parameters'][parameter['name']] = PARAM_VALUES[JAVA_MAPPING[parameter['value_type']](parameter['attributes'].get('data-format', False))]['convert'](proxy_argument['report_parameters'][parameter['name']])

            if self.data and self.data.get('output_type', False):
                proxy_argument['output_type']=self.data['output_type']

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
