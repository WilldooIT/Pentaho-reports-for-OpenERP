# -*- encoding: utf-8 -*-

import json

from openerp import models, fields, api, _
from openerp.exceptions import UserError, ValidationError

from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES
from openerp.addons.pentaho_reports.java_oe import OPENERP_DATA_TYPES, parameter_resolve_column_name

from ..report_formulae import *


class store_selections_wizard(models.TransientModel):
    _name = "ir.actions.store.selections.wiz"
    _description = "Store Report Selections Wizard"

    existing_selectionset_id = fields.Many2one('ir.actions.report.set.header', string='Selection Set', ondelete='set null')
    name = fields.Char(string='Selection Set Description', size=64, required=True)
    report_action_id = fields.Many2one('ir.actions.report.xml', string='Report Name', readonly=True)
    output_type = fields.Selection(VALID_OUTPUT_TYPES, string='Report format', help='Choose the format for the output')
    parameters_dictionary = fields.Text(string='parameter dictionary')
    detail_ids = fields.One2many('ir.actions.store.selections.detail.wiz', 'header_id', string='Selection Details')
    def_user_ids = fields.Many2many('res.users', 'ir_actions_store_selections_def_user_rel', 'header_id', 'user_id', string='Users (Default)')
    def_group_ids = fields.Many2many('res.groups', 'ir_actions_store_selections_def_group_rel', 'header_id', 'group_id', string='Groups (Default)')
    passing_wizard_id = fields.Many2one('ir.actions.report.promptwizard', string='Screen wizard - kept for "Cancel" button')

    @api.model
    def default_get(self, fields):
        if not self.env.context.get('active_id'):
            raise UserError(_('No active id passed.'))

        screen_wizard = self.env['ir.actions.report.promptwizard'].browse(self.env.context['active_id'])

        parameters_dictionary = json.loads(screen_wizard.parameters_dictionary)

        res = super(store_selections_wizard, self).default_get(fields)
        res.update({'existing_selectionset_id': screen_wizard.selectionset_id.id,
                    'name': screen_wizard.selectionset_id.name,
                    'report_action_id': screen_wizard.report_action_id.id,
                    'output_type': screen_wizard.output_type,
                    'parameters_dictionary': screen_wizard.parameters_dictionary,
                    'detail_ids': [],
                    'def_user_ids': [],
                    'def_group_ids': [],
                    'passing_wizard_id': screen_wizard.id,
                    })

        for index in range(0, len(parameters_dictionary)):
            res['detail_ids'].append((0, 0, {'variable': parameters_dictionary[index]['variable'],
                                             'label': parameters_dictionary[index]['label'],
                                             'counter': index,
                                             'type': parameters_dictionary[index]['type'],
                                             'x2m': parameter_can_2m(parameters_dictionary, index),
                                             'display_value': self.env['ir.actions.report.set.detail'].wizard_value_to_display(getattr(screen_wizard, parameter_resolve_column_name(parameters_dictionary, index)), parameters_dictionary, index),
                                             'calc_formula': getattr(screen_wizard, parameter_resolve_formula_column_name(parameters_dictionary, index)),
                                             }))

        if screen_wizard.selectionset_id:
            res['def_user_ids'] = [(6, 0, [u.id for u in screen_wizard.selectionset_id.def_user_ids])]
            res['def_group_ids'] = [(6, 0, [g.id for g in screen_wizard.selectionset_id.def_group_ids])]

        return res

    @api.multi
    def button_store_new(self):
        return self.button_store(replace=False)

    @api.multi
    def button_store_replace(self):
        return self.button_store(replace=True)

    def button_store(self, replace=True):
        header_obj = self.env['ir.actions.report.set.header']

        for wizard in self:
            clash_reports = header_obj.search([('name', '=', wizard.name)])
            if clash_reports and (not replace or len(clash_reports) > 1 or any(x.id != wizard.existing_selectionset_id.id for x in clash_reports)):
                # We enforce this so that users can uniquely identify a selection set.
                raise UserError(_('Selection Sets must have unique names across all reports.'))

            vals = {'name': wizard.name,
                    'report_action_id': wizard.report_action_id.id,
                    'output_type': wizard.output_type,
                    'parameters_dictionary': wizard.parameters_dictionary,
                    'detail_ids': [(5,)],
                    'def_user_ids': [(6, 0, [u.id for u in wizard.def_user_ids])],
                    'def_group_ids': [(6, 0, [g.id for g in wizard.def_group_ids])],
                    }

            if replace and wizard.existing_selectionset_id:
                wizard.existing_selectionset_id.write(vals)
                header = wizard.existing_selectionset_id
            else:
                header = header_obj.create(vals)

            for detail in wizard.detail_ids:
                self.env['ir.actions.report.set.detail'].create({'header_id': header.id,
                                                                 'variable': detail.variable,
                                                                 'label': detail.label,
                                                                 'counter': detail.counter,
                                                                 'type': detail.type,
                                                                 'x2m': detail.x2m,
                                                                 'display_value': detail.display_value,
                                                                 'calc_formula': detail.calc_formula,
                                                                })

        new_context = self.env.context.copy()
        new_context['populate_selectionset_id'] = header.id
        new_context['active_ids'] = []  # DEBUG - client will pass the active_ids on to the report call - This is behaviour we do not want, as the active_ids are from this wizard model.
        return {
                'view_mode': 'form',
                'res_model': 'ir.actions.report.promptwizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': new_context,
                }

    @api.multi
    def button_delete(self):
        if self.existing_selectionset_id:
            self.existing_selectionset_id.unlink()
        return self.button_cancel()

    @api.multi
    def button_cancel(self):
        if self.passing_wizard_id:
            new_context = self.env.context.copy()
            new_context['active_ids'] = []  # DEBUG - client will pass the active_ids on to the report call - This is behaviour we do not want, as the active_ids are from this wizard model.
            return {
                    'view_mode': 'form',
                    'res_model': 'ir.actions.report.promptwizard',
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                    'res_id': self.passing_wizard_id.id,
                    'context': new_context,
                    }
        return {'type': 'ir.actions.act_window_close'}

class store_selections_dets_wizard(models.TransientModel):
    _name = 'ir.actions.store.selections.detail.wiz'
    _description = "Store Report Selections Wizard"

    header_id = fields.Many2one('ir.actions.store.selections.wiz', string='Selections Set')
    variable = fields.Char(string='Variable Name', size=64)
    label = fields.Char(string='Label', size=64)
    counter = fields.Integer(string='Parameter Number')
    type = fields.Selection(OPENERP_DATA_TYPES, string='Data Type')
    x2m = fields.Boolean(string='Data List Type')
    display_value = fields.Text(string='Value')
    calc_formula = fields.Char(string='Formula')

    _order = 'counter'

    @api.onchange('calc_formula')
    def _onchange_calc_formula(self):
        if self.calc_formula:
            parameters = json.loads(self.header_id.parameters_dictionary)
            known_variables = {}
            for index in range(0, len(parameters)):
                known_variables[parameters[index]['variable']] = {'type': parameters[index]['type'],
                                                                  'x2m': parameter_can_2m(parameters, index),
                                                                  'calculated': False,
                                                                  }

            parsed_formula = self.env['ir.actions.report.set.formula'].validate_formula(self.calc_formula, self.type, self.x2m, known_variables)
            if parsed_formula.get('error'):
                raise UserError(parsed_formula['error'])
