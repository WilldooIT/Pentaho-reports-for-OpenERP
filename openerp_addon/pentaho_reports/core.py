import io
import os
import logging
import subprocess
import xmlrpclib
import base64

import netsvc
import pooler
import report
from osv import osv, fields

class Report(object):
	def __init__(self, name, cr, uid, ids, data, context):
		self.name = name
		self.cr = cr
		self.uid = uid
		self.ids = ids
		self.data = data
		self.model = self.data["model"]
		self.context = context or {}
		self.pool = pooler.get_pool(self.cr.dbname)
		self.report_path = None
		self.output_format = "pdf"

	def execute(self):
		self.logger = logging.getLogger()

		ids = self.pool.get("ir.actions.report.xml").search(self.cr, self.uid, [("report_name", "=", self.name[7:]), ("report_rml", "ilike", ".prpt")], context = self.context)
		data = self.pool.get("ir.actions.report.xml").read(self.cr, self.uid, ids[0], ["report_rml", "pentaho_report_output"])
		self.report_path = data["report_rml"]
		self.report_path = os.path.join(self.get_addons_path(), self.report_path)

		self.logger.debug("self.ids: %s" % self.ids)
		self.logger.debug("self.data: %s" % self.data)
		self.logger.debug("self.context: %s" % self.context)
		self.logger.info("Requested report: '%s'" % self.report_path)

		output_report_data = base64.decodestring(self.execute_report())

		return (output_report_data, self.output_format)
	
	def get_addons_path(self):
		return os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

	def execute_report(self):
		locale = self.context.get("lang", "en_US")

		user_model = self.pool.get("res.users")
		current_user = user_model.browse(self.cr, self.uid, self.uid)

		encoded_pdf_string = ""
		with open(self.report_path, "rb") as prpt_file:
			encoded_prpt_file = io.BytesIO()
			base64.encode(prpt_file, encoded_prpt_file)

			#TODO: Make this configurable from inside the UI
			proxy = xmlrpclib.ServerProxy("http://localhost:8090")
			proxy_argument = {"PRPTFile": encoded_prpt_file.getvalue(), "OEHost": "localhost", "OEPort": "8069", "OEDB": self.cr.dbname, "OEUser": current_user.login, "OEPass": current_user.password, "ids": self.ids}
			self.logger.debug("Calling proxy with arg: %s" % proxy_argument)
			encoded_pdf_string = proxy.report.execute(proxy_argument)
			self.logger.debug("Report server returned: %s" % encoded_pdf_string)
			
		return encoded_pdf_string

class PentahoReportOpenERPInterface(report.interface.report_int):
	def __init__(self, name, model, parser = None):
		if name in netsvc.Service._services:
			del netsvc.Service._services[name]

		super(PentahoReportOpenERPInterface, self).__init__(name)
		self.model = model
		self.parser = parser

	def create(self, cr, uid, ids, data, context):
		name = self.name

		report_instance = Report(name, cr, uid, ids, data, context)

		return report_instance.execute()

def register_pentaho_report(report_name, model_name):
	name = "report.%s" % report_name

	if name in netsvc.Service._services:
		if isinstance(netsvc.Service._services[name], PentahoReportOpenERPInterface):
			return
		del netsvc.Service._services[name]
	
	PentahoReportOpenERPInterface(name, model_name)

#Following OpenERP's (messed up) naming convention
class ir_actions_report_xml(osv.osv):
	_inherit = "ir.actions.report.xml"

	def register_all(self, cr):
		cr.execute("SELECT * FROM ir_act_report_xml WHERE report_rml ILIKE '%.prpt' ORDER BY id")
		records = cr.dictfetchall()
		for record in records:
			register_pentaho_report(record["report_name"], record["model"])

		return super(ir_actions_report_xml, self).register_all(cr)

ir_actions_report_xml()
