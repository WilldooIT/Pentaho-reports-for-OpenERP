from openerp.osv import fields, orm
from openerp.tools.translate import _

import json


class ReportSchedulerSelnSets(orm.Model):
    _inherit = "ir.actions.report.scheduler"


    def _check_overriding_values(self, cr, uid, line, values_so_far, context=None):
        result = super(ReportSchedulerSelnSets, self)._check_overriding_values(cr, uid, line, values_so_far, context=context)
        if line.selectionset_id and values_so_far:
            result.update(self.pool.get('ir.actions.report.set.header').selections_to_dictionary(cr, uid, line.selectionset_id.id, json.loads(values_so_far.get('parameters_dictionary')), values_so_far.get('x2m_unique_id'), context=context))
        return result

class ReportSchedulerLinesSelnSets(orm.Model):
    _inherit = "ir.actions.report.scheduler.line"

    _columns = {'selectionset_id': fields.many2one('ir.actions.report.set.header', 'Selections', ondelete='cascade'),
                }

    def onchange_selectionset(self, cr, uid, ids, selectionset_id, context=None):
        result = {}
        if selectionset_id:
            result['value']={'report_id': self.pool.get('ir.actions.report.set.header').browse(cr, uid, selectionset_id, context=context).report_action_id.id}
        return result

    def onchange_report_p(self, cr, uid, ids, report_id, selectionset_id, context=None):
        if selectionset_id:
            selnset = self.pool.get('ir.actions.report.set.header').browse(cr, uid, selectionset_id, context=context)
            if report_id != selnset.report_action_id.id:
                return {'value': {'report_id': selnset.report_action_id.id}}

        return self.onchange_report(cr, uid, ids, report_id, context=context)
