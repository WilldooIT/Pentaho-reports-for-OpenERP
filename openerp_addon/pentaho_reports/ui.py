import os
import base64
import unicodedata

from osv import osv, fields

import core

class report_xml_file(osv.osv):
	_name = "ir.actions.report.xml.file"
	_columns = {
		"file": fields.binary("File", required = True, filters = "*.prpt", help = ""),
		"filename": fields.char("Filename", size = 256, required = False, help = ""),
		"report_id": fields.many2one("ir.actions.report.xml", "Report", required = True, ondelete = "cascade", help = ""),
		"default": fields.boolean("Default", help = "")
	}

	def create(self, cr, uid, vals, context = None):
		result = super(report_xml_file, self).create(cr, uid, vals, context=context)
		self.pool.get("ir.actions.report.xml").update(cr, uid, [vals["report_id"]], context=context)

		return result
	
	def write(self, cr, uid, ids, vals, context = None):
		result = super(report_xml_file, self).write(cr, uid, ids, vals, context=context)

		for attachment in self.browse(cr, uid, ids, context=context):
			self.pool.get("ir.actions.report.xml").update(cr, uid, [attachment.report_id.id], context=context)

		return result
	
report_xml_file()

#
class report_xml(osv.osv):
	_name = "ir.actions.report.xml"
	_inherit = "ir.actions.report.xml"
	_columns = {
		"pentaho_report_output_type": fields.selection([
			("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV"),
			("xls", "Excel"), ("rtf", "RTF"), ("txt", "Plain text")
		], "Output format"),
		"pentaho_report_file_ids": fields.one2many("ir.actions.report.xml.file", "report_id", "Files", help = ""),
		"pentaho_report_model_id": fields.many2one("ir.model", "Model", help = ""),
		"is_pentaho_report": fields.boolean("Is this a Pentaho report?", help = ""),
		"menu_item": fields.boolean('Create menu item'),

	}
	_defaults = {
		"pentaho_report_output_type": lambda self, cr, uid, context: context and context.get("is_pentaho_report") and "pdf" or False
	}


	def update_menu(self, cr, uid, id, unlink=False, context=None):

		do_add_item = not unlink and self.browse(cr, uid, id, context=context).menu_item

		# find the menu item and
		#	a) remove if not "do_add_item"
		#	b) update if "do_add_item"
		# or
		#	c) create if not found and "do_add_item"
		# don't forget security groups.


	def create(self, cr, uid, vals, context = None):
		if context and context.get("is_pentaho_report"):
			vals["model"] = self.pool.get("ir.model").browse(cr, uid, vals["pentaho_report_model_id"], context=context).model
			vals["type"] = "ir.actions.report.xml"
			vals["report_type"] = "pdf"
			vals["is_pentaho_report"] = True

		res = super(report_xml, self).create(cr, uid, vals, context=context)
		self.update_menu(cr, uid, res, context=context)
		return res


	def write(self, cr, uid, ids, vals, context = None):
		if context and context.get("is_pentaho_report"):
			if "pentaho_report_model_id" in vals:
				vals["model"] = self.pool.get("ir.model").browse(cr, uid, vals["pentaho_report_model_id"], context=context).model
			vals["type"] = "ir.actions.report.xml"
			vals["report_type"] = "pdf"
			vals["is_pentaho_report"] = True

		res = super(report_xml, self).write(cr, uid, ids, vals, context=context)
		for id in ids:
			self.update_menu(cr, uid, id, context=context)
		return res


	def unlink(self, cr, uid, ids, context=None):
		for id in ids:
			self.update_menu(cr, uid, id, unlink=True, context=context)
		return super(report_xml, self).unlink(cr, uid, ids, context=context)


	def update(self, cr, uid, ids, context = None):
		for report in self.browse(cr, uid, ids):
			has_default = False

			for attachment in report.pentaho_report_file_ids:
				content = attachment.file
				file_name = attachment.filename
				if not file_name or not content:
					continue
				path = self.save_content_to_file(file_name, content)
				if file_name.endswith(".prpt"):
					if attachment.default:
						if has_default:
							raise osv.except_osv("Error", "More than one report file marked as default!")
						has_default = True

						self.write(cr, uid, [report.id], {"report_rml": path})
						values_id = self.pool.get("ir.values").search(cr, uid, [("value", "=", "ir.actions.report.xml,%s" % report.id)])
						data = {
							"name": report.name,
							"model": report.model,
							"key": "action",
							"object": True,
							"key2": "client_print_multi",
							"value": "ir.actions.report.xml,%s" % report.id
						}
						if not values_id:
							values_id = self.pool.get("ir.values").create(cr, uid, data, context=context)
						else:
							self.pool.get("ir.values").write(cr, uid, values_id, data, context=context)
							values_id = values_id[0]
			if not has_default:
				raise osv.except_osv("Error", "No report marked as default.")
			
			core.register_pentaho_report(report.report_name)
		return True
	
	def save_content_to_file(self, name, value):
		path = os.path.abspath(os.path.dirname(__file__))
		path += os.sep + "custom_reports" + os.sep + name

		with open(path, "wb+") as report_file:
			report_file.write(base64.decodestring(value))

		path = "pentaho_reports" + os.sep + "custom_reports" + os.sep + name
		return path

report_xml()
