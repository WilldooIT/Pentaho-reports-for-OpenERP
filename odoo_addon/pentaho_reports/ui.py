# -*- encoding: utf-8 -*-

import os
import base64
from openerp.tools.safe_eval import safe_eval
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from openerp.tools import config

import core

from java_oe import JAVA_MAPPING, check_java_list, PARAM_VALUES

ADDONS_PATHS = config['addons_path'].split(",")


class report_xml(models.Model):
    _inherit = 'ir.actions.report.xml'

    report_type = fields.Selection(selection_add=[('pentaho','Pentaho Report')])
    pentaho_report_output_type = fields.Selection([("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV"), ("xls", "Excel"), ("xlsx", "Excel 2007"), ("rtf", "RTF"), ("txt", "Plain text")],
                                                   string = 'Output format')
    pentaho_report_model_id = fields.Many2one('ir.model', string='Model')
    pentaho_file = fields.Binary(string='File', filters='*.prpt')
    pentaho_filename = fields.Char(string='Filename', required=False)
    linked_menu_id = fields.Many2one('ir.ui.menu', string='Linked menu item', select=True)
    created_menu_id = fields.Many2one('ir.ui.menu', string='Created menu item', copy=False)
    # This is not displayed on the client - it is a trigger to indicate that
    # a prpt file needs to be loaded - normally it is loaded by the client interface
    # In this case, the filename should be specified with a module path.
    pentaho_load_file = fields.Boolean(string='Load prpt file from filename')

    @api.onchange('report_type')
    def _onchange_report_type(self):
        if self.report_type == 'pentaho':
            self.auto = False
            self.pentaho_report_output_type = 'pdf'

            if self.model:
                if not self.pentaho_report_model_id or self.pentaho_report_model_id.model != self.model:
                    self.pentaho_report_model_id = self.env['ir.model'].search([('model', '=', self.model)], limit=1)
        else:
            if self.pentaho_report_model_id:
                self.model = self.pentaho_report_model_id.model

    @api.onchange('pentaho_report_model_id')
    def _onchange_model_id(self):
        if self.pentaho_report_model_id:
            self.model = self.pentaho_report_model_id.model
        else:
            self.model = False

    @api.model
    def create_menu(self, vals):
        view = self.env['ir.ui.view'].search([('model', '=', 'ir.actions.report.promptwizard'), ('type', '=', 'form')], limit=1)

        action_vals = {'name': vals.get('name', 'Pentaho Report'),
                       'res_model': 'ir.actions.report.promptwizard',
                       'type' : 'ir.actions.act_window',
                       'view_type': 'form',
                       'view_mode': 'tree,form',
                       'view_id' : view.id,
                       'context' : "{'service_name': '%s'}" % vals.get('report_name', ''),
                       'target' : 'new',
                       }
        action = self.env['ir.actions.act_window'].create(action_vals)

        result = self.env['ir.ui.menu'].sudo().create({
                                                       'name': vals.get('name' ,'Pentaho Report'),
                                                       'sequence': 10,
                                                       'parent_id': vals['linked_menu_id'],
                                                       'groups_id': vals.get('groups_id', []),
                                                       'icon': 'STOCK_PRINT',
                                                       'action': 'ir.actions.act_window,%d' % (action.id,),
                                                       })
        return result

    @api.multi
    def delete_menu(self):
        for report in self:
            if report.created_menu_id:
                if report.created_menu_id.action._model._name == 'ir.actions.act_window':
                    report.created_menu_id.action.unlink()
                report.created_menu_id.action.sudo().unlink()

    @api.multi
    def update_menu(self):
        for report in self:
            if report.created_menu_id and not report.linked_menu_id:
                report.delete_menu()
            if report.report_type == 'pentaho' and report.linked_menu_id:
                groups_id = [(6, 0, map(lambda x: x.id, report.groups_id))]
                if not report.created_menu_id:
                    report.created_menu_id = self.create_menu({'name': report.name,
                                                               'linked_menu_id': report.linked_menu_id.id,
                                                               'report_name': report.report_name,
                                                               'groups_id': groups_id,
                                                               })
                else:
                    if report.created_menu_id.action._model._name == 'ir.actions.act_window':
                        existing_context = safe_eval(report.created_menu_id.action.context)
                        new_context = existing_context if type(existing_context) == dict else {}
                        new_context['service_name'] = report.report_name or ''
                        report.created_menu_id.action.write({'name': report.name or 'Pentaho Report',
                                                             'context': str(new_context),
                                                             })
                    report.created_menu_id.sudo().write({'name': report.name or 'Pentaho Report',
                                                         'parent_id': report.linked_menu_id.id,
                                                         'groups_id': groups_id,
                                                         })

    @api.model
    def create(self, vals):
        if vals.get('report_type','') == 'pentaho':
            vals.update({'type': 'ir.actions.report.xml',
                         'auto': False,
                         })
            if vals.get('linked_menu_id'):
                vals['created_menu_id'] = self.with_context(skip_update_pentaho = True).create_menu(vals).id

        res = super(report_xml, self).create(vals)
        res.update_pentaho()
        return res

    @api.multi
    def write(self, vals):
        if vals.get('report_type','') == 'pentaho':
            vals.update({'type': 'ir.actions.report.xml',
                         'auto': False,
                         })
        res = super(report_xml, self).write(vals)
        self.with_context(skip_update_pentaho = True).update_menu()
        self.update_pentaho()
        return res

    @api.multi
    def unlink(self):
        self.delete_menu()
#
#TODO: this code can be removed as it should now be handled by the v9 UI
#
#         for r in self:
#             self.env['ir.values'].search([('value', '=', 'ir.actions.report.xml,%s' % r.id)]).sudo().unlink()
        return super(report_xml, self).unlink()

    @api.multi
    def update_pentaho(self):
        if self.env.context.get('skip_update_pentaho'):
            return
        for report in self:
            if report.report_type == 'pentaho':
                if report.pentaho_filename:
                    if report.pentaho_load_file:
                        # if we receive a filename and no content, this has probably been loaded by a process other than the standard client, such as a data import
                        # in this case, we expect the filename to be a fully specified file within a module from which we load the file data
                        report.with_context(skip_update_pentaho = True).write({'pentaho_filename': os.path.basename(report.pentaho_filename),
                                                                               'pentaho_file': self.read_content_from_file(report.pentaho_filename),
                                                                               'pentaho_load_file': False
                                                                               })
                        report = self.browse(report.id)

                    # we are no longer relying on report_rml to contain a name at all - for clarity, though, still store it...
                    report.with_context(skip_update_pentaho = True).write({'report_rml': report.pentaho_filename})
                elif report.pentaho_file:
                    report.with_context(skip_update_pentaho = True).write({'pentaho_file': False})

    def read_content_from_file(self, name):
        path_found = False
        for addons_path in ADDONS_PATHS:
            try:
                os.stat(addons_path + os.sep + name)
                path_found = True
                break
            except:
                pass
        if not path_found:
            raise ValidationError(_('Could not locate path for file %s') % name)
        path = addons_path + os.sep + name

        with open(path, "rb") as report_file:
            data = base64.encodestring(report_file.read())
        return data
