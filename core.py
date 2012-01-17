import os
import logging
import tempfile
import subprocess

import netsvc
import pooler
import report
from osv import osv, fields

class PentahoReport(object):
	def __init__(self, file_name = "", path_prefix = ""):
		self._report_path = file_name
		self._path_prefix = path_prefix.strip()
		if self._path_prefix and self._path_prefix[-1] != '/':
			self._path_prefix += '/'

	def get_report_store_directory(self):
		return os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'report', '')

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
		self.report = None
		self.temporary_files = []
		self.output_format = "pdf"
		self.path = os.path.abspath(os.path.dirname(__file__))

	def execute(self):
		#CHNG: Don't use OpenERP's netsvc logger
		logger = logging.getLogger()

		ids = self.pool.get("ir.actions.report.xml").search(self.cr, self.uid, [("report_name", "=", self.name[7:]), ("report_rml", "ilike", ".prpt")], context = self.context)
		data = self.pool.get("ir.actions.report.xml").read(self.cr, self.uid, ids[0], ["report_rml", "pentaho_report_output"])
		self.report_path = data["report_rml"]
		self.report_path = os.path.join(self.get_addons_path(), self.report_path)

		logger.info("Requested report: '%s'" % self.report_path)

		self.report = PentahoReport(self.report_path)

		fd, output_file_name = tempfile.mkstemp()
		os.close(fd)
		self.temporary_files.append(output_file_name)

		logger.info("Temporary output file: '%s'" % output_file_name)

		self.execute_report(output_file_name)

		with open(output_file_name, "rb") as output_report_file:
			output_report_data = output_report_file.read()

		for temp_file in self.temporary_files:
			try:
				pass
				#os.unlink(temp_file)
			except os.error, e:
				logger.warn("Couldn't remove file '%s'." % temp_file)
		self.temporary_files = []

		return (output_report_data, self.output_format)
	
	def get_addons_path(self):
		return os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

	def execute_report(self, output_file):
		locale = self.context.get("lang", "en_US")

		user_model = self.pool.get("res.users")
		current_user = user_model.browse(self.cr, self.uid, self.uid)
		command = [os.path.join(self.path, "run_report.sh"), self.report_path, output_file, "OEHost=localhost", "OEPort=8069", "OEDB=%s" % self.cr.dbname, "OEUser=%s" % current_user.login, "OEPass=%s" % current_user.password]
		subprocess.call(command)

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
