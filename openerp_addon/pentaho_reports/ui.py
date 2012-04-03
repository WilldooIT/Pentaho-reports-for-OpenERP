import os
import base64
import unicodedata

from osv import osv, fields

import core


#
class report_xml(osv.osv):
    _name = "ir.actions.report.xml"
    _inherit = "ir.actions.report.xml"
    _columns = {
        "pentaho_report_output_type": fields.selection([
            ("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV"),
            ("xls", "Excel"), ("rtf", "RTF"), ("txt", "Plain text")
        ], "Output format"),
        "pentaho_report_model_id": fields.many2one("ir.model", "Model", help = ""),
        "pentaho_file": fields.binary("File", filters = "*.prpt"),
        "pentaho_filename": fields.char("Filename", size = 256, required = False),
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
        default.update({'created_menu_id' : 0})
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
            vals['auto'] = False

        if vals.get('linked_menu_id', False):
            vals['created_menu_id'] = self.create_menu(cr, uid, vals, context=context)

        res = super(report_xml, self).create(cr, uid, vals, context=context)

        self.update_pentaho(cr, uid, [res], context=context)

        return res




    def write(self, cr, uid, ids, vals, context = None):
        if context is None:
            context={}

        if context.get("is_pentaho_report", False):
            if "pentaho_report_model_id" in vals:
                vals["model"] = self.pool.get("ir.model").browse(cr, uid, vals["pentaho_report_model_id"], context=context).model
            vals["type"] = "ir.actions.report.xml"
            vals["report_type"] = "pdf"
            vals["is_pentaho_report"] = True
            vals['auto'] = False

        res = super(report_xml, self).write(cr, uid, ids, vals, context=context)

        for r in self.browse(cr, uid, ids if isinstance(ids, list) else [ids], context=context):
            created_menu_id = self.update_menu(cr, uid, r, context=context)
            if created_menu_id != r.created_menu_id:
                super(report_xml, self).write(cr, uid, [r.id], {'created_menu_id': created_menu_id}, context=context)

        self.update_pentaho(cr, uid, ids if isinstance(ids, list) else [ids], context=context)

        return res


    def unlink(self, cr, uid, ids, context=None):

        values_obj=self.pool.get('ir.values')

        for r in self.browse(cr, uid, ids, context=context):
            if r.created_menu_id:
                self.delete_menu(cr, uid, r.created_menu_id.id, context=context)

            values_obj.unlink(cr, uid, values_obj.search(cr, uid, [("value", "=", "ir.actions.report.xml,%s" % r.id)]), context=context)

        return super(report_xml, self).unlink(cr, uid, ids, context=context)




    def update_pentaho(self, cr, uid, ids, context = None):

        values_obj=self.pool.get('ir.values')

        for report in self.browse(cr, uid, ids):

            values_ids = values_obj.search(cr, uid, [("value", "=", "ir.actions.report.xml,%s" % report.id)])

            if report.pentaho_filename or report.pentaho_file:
                path = self.save_content_to_file(report.pentaho_filename, report.pentaho_file)

                super(report_xml, self).write(cr, uid, [report.id], {"report_rml": path})

                if not report.linked_menu_id and report.pentaho_filename.endswith(".prpt"):
                    data = {
                            "name": report.name,
                            "model": report.model,
                            "key": "action",
                            "object": True,
                            "key2": "client_print_multi",
                            "value": "ir.actions.report.xml,%s" % report.id
                            }
                    if not values_ids:
                        values_obj.create(cr, uid, data, context=context)
                    else:
                        values_obj.write(cr, uid, values_ids, data, context=context)
                    values_ids = []

                core.register_pentaho_report(report.report_name)

            if context.get('is_pentaho_report', False) and values_ids:
                values_obj.unlink(cr, uid, values_ids, context=context)

        return True




    def save_content_to_file(self, name, value):
        path = os.path.abspath(os.path.dirname(__file__))
        path += os.sep + "custom_reports" + os.sep + name

        with open(path, "wb+") as report_file:
            report_file.write(base64.decodestring(value))

        path = "pentaho_reports" + os.sep + "custom_reports" + os.sep + name
        return path

report_xml()
