from openerp import models, fields, api, _
import datetime
from openerp import netsvc
import json
import openerp

from openerp.addons.pentaho_reports.java_oe import parameter_resolve_column_name

class ReportScheduler(models.Model):
    _name = "ir.actions.report.scheduler"
    _description = "Report Scheduler"

    name = fields.Char(string='Name', size=64, required=True)
    description = fields.Text(string='Description')
    action_type = fields.Selection([('email', 'Send Email'), ('notification', 'Send to User Notifications'), ('both', 'Notification and Email')], string='Type', required=True)
    line_ids = fields.One2many('ir.actions.report.scheduler.line', 'scheduler_id', string='List of Reports', help="Enter a list of reports to run.")
    user_list = fields.Many2many('res.users', 'rep_sched_user_rel', 'sched_id', 'user_id', string='List of Users', help="Enter a list of users to receive the reports.")

    def dt_to_local(self, dt):
        """Convert a UTC date/time to local.
    
        @param dt: A date/time with a UTC time.
        @param context: This must contain the user's local timezone
            as context['tz'].
        """
        # Returns 'NONE' if user has no tz defined or tz not passed
        # in the context.
        return fields.Datetime.context_timestamp(self, dt)

    @api.multi
    def _send_reports(self, reports):
        self.ensure_one()
        run_on = datetime.datetime.now()
        run_on_local = self.dt_to_local(run_on)
        if not run_on_local:
            run_on_local = run_on

        report_summary = """Run on:%s

%s""" % (run_on_local.strftime('%d-%b-%Y at %H:%M:%S'), self.description or '')

#        attachments={}
#        for rpt_name, content, type in reports:
#            attach_fname = "%s-%s.%s" % (rpt_name, run_on_local.strftime('%Y-%m-%d-%H-%M-%S'), type)
#            attachments[attach_fname] = content

        attachments = self.env['ir.attachment']
        for rpt_name, content, type in reports:
            attachments += attachments.create({'datas': content.encode('base64'),
                                               'name': rpt_name,
                                               'datas_fname': '%s.%s' % (rpt_name, type),
                                               })

        if self.action_type in ('email', 'both'):
            email_addresses = [x.email for x in self.user_list if x.email]
            if email_addresses:
                msg = self.env['mail.mail'].create({'subject' : self.name,
                                                    'email_from' : self.env.user.email,
                                                    'email_to' : ','.join(email_addresses),
                                                    'attachment_ids' : [(6, 0, attachments.ids)],
                                                    'body_html' : report_summary,
                                                    })
                msg.send()

        if self.action_type in ('notification', 'both'):
            receiver_ids = [x.partner_id.id for x in self.user_list]
            if receiver_ids:
                self.env['mail.message'].create({'subject': self.name,
                                                 'type': "notification",
                                                 'partner_ids': [(6, 0, receiver_ids)],
                                                 'notified_partner_ids': [(6, 0, receiver_ids)],
                                                 'attachment_ids': [(6, 0, attachments.ids)],
                                                 'body': report_summary,
                                                 })

    @api.model
    def _check_overriding_values(self, line, values_so_far):
        return {}

    @api.model
    def _report_variables(self, line):
        result = {}
        if line.report_type == 'pentaho':
            # attempt to fill the prompt wizard as if we had gone in to it from a menu and then run.
            promptwizard_obj = self.env['ir.actions.report.promptwizard']

            # default_get creates a dictionary of wizard default values
            values = promptwizard_obj.default_get_external(line.report_id.id)
            # this hook is provided to allow for selection set values, which are not necessarily installed
            values.update(self._check_overriding_values(line, values))

            if values:
                # now convert virtual screen values from prompt wizard to values which can be passed to the report action
                result = {'output_type': values.get('output_type'),
                          'variables': {}}
                parameters = json.loads(values.get('parameters_dictionary'))
                for index in range(0, len(parameters)):
                    result['variables'][parameters[index]['variable']] = promptwizard_obj.decode_wizard_value(parameters, index, values[parameter_resolve_column_name(parameters, index)])

        return result

    @api.multi
    def _run_all(self):
        for sched in self:
            if sched.line_ids or sched.user_list:
                report_output = []
                for line in sched.line_ids:
                    report = line.report_id
                    datas = {'model': sched._name,
                             }
                    datas.update(sched._report_variables(line))
                    if report.report_type in ['qweb-html', 'qweb-pdf']:
                        content, type = self.pool['report'].get_pdf(self.env.cr, self.env.uid, [], report.report_name, context=self.env.context), 'pdf'
                    else:
                        content, type = openerp.report.render_report(self.env.cr, self.env.uid, [], report.report_name, datas, self.env.context)
                    report_output.append((report.name, content, type))
                if report_output:
                    sched._send_reports(report_output)

    @api.multi
    def button_run_now(self):
        self._run_all()

    @api.model
    def run_report_email_scheduler(self, scheduled_name=''):
        self.search([('name', '=', scheduled_name)])._run_all()


class ReportSchedulerLines(models.Model):
    _name = "ir.actions.report.scheduler.line"
    _description = "Report Scheduler Lines"

    scheduler_id = fields.Many2one('ir.actions.report.scheduler', string='Scheduler')
    report_id = fields.Many2one('ir.actions.report.xml', string='Report', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence')
    report_type = fields.Selection(string='Report Type', related='report_id.report_type', readonly=True)
    model = fields.Char(string='Object', related='report_id.model', readonly=True)
    type = fields.Char(string='Action Type', related='report_id.type', readonly=True)

    _order='sequence'
