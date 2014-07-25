from openerp import fields, models, api, _

import json


class ReportSchedulerSelnSets(models.Model):
    _inherit = "ir.actions.report.scheduler"


    def _check_overriding_values(self, cr, uid, line, values_so_far, context=None):
        result = super(ReportSchedulerSelnSets, self)._check_overriding_values(cr, uid, line, values_so_far, context=context)
        if line.selectionset_id and values_so_far:
            result.update(self.pool.get('ir.actions.report.set.header').selections_to_dictionary(cr, uid, line.selectionset_id.id, json.loads(values_so_far.get('parameters_dictionary')), values_so_far.get('x2m_unique_id'), context=context))
        return result

class ReportSchedulerLinesSelnSets(models.Model):
    _inherit = "ir.actions.report.scheduler.line"

    selectionset_id = fields.Many2one('ir.actions.report.set.header', string='Selections', ondelete='cascade')

    @api.onchange('selectionset_id')
    def _onchange_selectionset_id(self):
        if self.selectionset_id:
            self.report_id = self.selectionset_id.report_action_id.id
