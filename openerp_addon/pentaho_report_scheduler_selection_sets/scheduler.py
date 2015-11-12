from openerp import fields, models, api, _
from openerp.exceptions import Warning

import json

class ReportSchedulerSelnSets(models.Model):
    _inherit = "ir.actions.report.scheduler"

    @api.model
    def _check_overriding_values(self, line, values_so_far):
        result = super(ReportSchedulerSelnSets, self)._check_overriding_values(line, values_so_far)
        if line.selectionset_id and values_so_far:
            result.update(line.selectionset_id.selections_to_dictionary(json.loads(values_so_far.get('parameters_dictionary')), values_so_far.get('x2m_unique_id')))
        return result

class ReportSchedulerLinesSelnSets(models.Model):
    _inherit = "ir.actions.report.scheduler.line"

    selectionset_id = fields.Many2one('ir.actions.report.set.header', string='Selections', ondelete='cascade')

    @api.onchange('selectionset_id')
    def _onchange_selectionset_id(self):
        if self.selectionset_id:
            self.report_id = self.selectionset_id.report_action_id.id
