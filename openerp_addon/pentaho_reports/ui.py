# todo:
#    ir.actions.report.xml.file - is not needed - integrate directly on ir.actions.report.xml
#    xml building improvement


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
    
    def update(self, cr, uid, ids, vals, context = None):
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
        'linked_menu_id' : fields.many2one('ir.ui.menu','Linked menu item', select=True),
        'created_menu_id' : fields.many2one('ir.ui.menu','Created menu item'),

    }
    _defaults = {
        "pentaho_report_output_type": lambda self, cr, uid, context: context and context.get("is_pentaho_report") and "pdf" or False
    }


    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default = default.copy()
        default['created_menu_id'] = 0
        return super(report_xml, self).copy(cr, uid, id, default, context=context)


    def create_menu(self, cr, uid, vals, context=None):

        view_ids=self.pool.get('ir.ui.view').search(cr, uid, [('model', '=', 'ir.actions.report.promptwizard'),('type','=','form')], context=context)

        action_vals = {'name': vals.get('name','Pentaho Report'),
                       'res_model': 'ir.actions.report.promptwizard',
                       'type' : 'ir.actions.act_window',
                       'view_type': 'form',
                       'view_mode': 'tree,form',
                       'view_id' : view_ids and view_ids[0] or 0,
                       'context' : "{'service_name' : '%s'}" % vals.get('report_name',''),
                       'target' : 'new',
                       }
        action_id = self.pool.get('ir.actions.act_window').create(cr, uid, action_vals, context=context)

        action = 'ir.actions.act_window,652'
        result = self.pool.get('ir.ui.menu').create(cr, uid, {'name' : vals.get('name' ,'Pentaho Report'),
                                                              'sequence' : 10,
                                                              'parent_id' : vals['linked_menu_id'],
                                                              'groups_id' : vals.get('groups_id',[]),
                                                              'icon' : 'STOCK_PRINT',
                                                              'action' : 'ir.actions.act_window,%d' % (action_id,),
                                                              }, context=context)

        return result


    def delete_menu(self, cr, uid, menu_id, context=None):
        action = self.pool.get('ir.ui.menu').browse(cr, uid, menu_id, context=context).action
        if action and action._model._name == 'ir.actions.act_window':
            self.pool.get('ir.actions.act_window').unlink(cr, uid, [action.id], context=context)
        result = self.pool.get('ir.ui.menu').unlink(cr, uid, [menu_id], context=context)
        return result


    def update_menu(self, cr, uid, action_report, context=None):

        if action_report.created_menu_id and not action_report.linked_menu_id:
            self.delete_menu(cr, uid, action_report.created_menu_id.id, context=context)

        if action_report.linked_menu_id:
            groups_id = [(6, 0, map(lambda x: x.id, action_report.groups_id))]
            if not action_report.created_menu_id:
                result = self.create_menu(cr, uid, {'name' : action_report.name,
                                                    'linked_menu_id': action_report.linked_menu_id.id,
                                                    'report_name' : action_report.report_name,
                                                    'groups_id' : groups_id,
                                                    }, context=context)
            else:
                action = action_report.created_menu_id.action
                if action and action._model._name == 'ir.actions.act_window':
                    self.pool.get('ir.actions.act_window').write(cr, uid, [action.id], {'name' : action_report.name or 'Pentaho Report',
                                                                                        'context' : "{'service_name' : '%s'}" % action_report.report_name or ''
                                                                                        }, context=context)

                self.pool.get('ir.ui.menu').write(cr, uid, [action_report.created_menu_id.id], {'name' : action_report.name or 'Pentaho Report',
                                                                                             'parent_id' : action_report.linked_menu_id.id,
                                                                                             'groups_id' : groups_id,
                                                                                             }, context=context)
                result = action_report.created_menu_id.id
        else:
            result = 0

        return result


    def create(self, cr, uid, vals, context = None):
        if context is None:
            context={}

        if context.get("is_pentaho_report",False):
            vals["model"] = self.pool.get("ir.model").browse(cr, uid, vals["pentaho_report_model_id"], context=context).model
            vals["type"] = "ir.actions.report.xml"
            vals["report_type"] = "pdf"
            vals["is_pentaho_report"] = True

        if vals.get('linked_menu_id', False):
            vals['created_menu_id'] = self.create_menu(cr, uid, vals, context=context)

        return super(report_xml, self).create(cr, uid, vals, context=context)


    def write(self, cr, uid, ids, vals, context = None):
        if context is None:
            context={}

        if context.get("is_pentaho_report", False):
            if "pentaho_report_model_id" in vals:
                vals["model"] = self.pool.get("ir.model").browse(cr, uid, vals["pentaho_report_model_id"], context=context).model
            vals["type"] = "ir.actions.report.xml"
            vals["report_type"] = "pdf"
            vals["is_pentaho_report"] = True

        res = super(report_xml, self).write(cr, uid, ids, vals, context=context)

        for r in self.browse(cr, uid, ids if isinstance(ids, list) else [ids], context=context):
            created_menu_id = self.update_menu(cr, uid, r, context=context)
            if created_menu_id != r.created_menu_id:
                super(report_xml, self).write(cr, uid, [r.id], {'created_menu_id': created_menu_id}, context=context)

        return res


    def unlink(self, cr, uid, ids, context=None):
        for r in self.browse(cr, uid, ids, context=context):
            if r.created_menu_id:
                self.delete_menu(cr, uid, r.created_menu_id.id, context=context)
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
