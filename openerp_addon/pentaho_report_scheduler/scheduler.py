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

    def dt_to_local(self, cr, uid, dt, context=None):
        """Convert a UTC date/time to local.
    
        @param dt: A date/time with a UTC time.
        @param context: This must contain the user's local timezone
            as context['tz'].
        """
        # Returns 'NONE' if user has no tz defined or tz not passed
        # in the context.
        return fields.datetime.context_timestamp(cr, uid, timestamp=dt, context=context)

    def _send_reports(self, cr, uid, sched, reports, context=None):
        run_on = datetime.datetime.now()
        run_on_local = self.dt_to_local(cr, uid, run_on, context=context)
        if not run_on_local:
            run_on_local = run_on

        user_obj = self.pool.get('res.users')
        mail_message_obj = self.pool.get('mail.message')
        mail_mail_obj = self.pool.get('mail.mail')
        attachment_obj = self.pool.get('ir.attachment')
        report_summary = """Run on:%s

%s""" % (run_on_local.strftime('%d-%b-%Y at %H:%M:%S'),sched.description or '')

#        attachments={}
#        for rpt_name, content, type in reports:
#            attach_fname = "%s-%s.%s" % (rpt_name, run_on_local.strftime('%Y-%m-%d-%H-%M-%S'), type)
#            attachments[attach_fname] = content

        attachment_ids = []
        for rpt_name, content, type in reports:
            attachment_ids.append(attachment_obj.create(cr, uid, {'datas': content.encode('base64'),
                                                                  'name': rpt_name,
                                                                  'datas_fname': '%s.%s' % (rpt_name, type),
                                                                  },
                                                        context=context))

        if sched.action_type in ('email', 'both'):
            email_addresses = [x.user_email for x in sched.user_list if x.user_email]
            if email_addresses:
                msg_id = mail_mail_obj.create(cr, uid, {'subject' : sched.name,
                                                        'email_from' : user_obj.browse(cr, uid, uid, context=context).user_email,
                                                        'email_to' : ','.join(email_addresses),
                                                        'attachment_ids' : [(6, 0, attachment_ids)],
                                                        'body_html' : report_summary,
                                                        }
                                              ,context=context)
                mail_mail_obj.send(cr, uid, [msg_id], context=context)

        if sched.action_type in ('notification', 'both'):
            receiver_ids = [x.partner_id.id for x in sched.user_list]
            if receiver_ids:
                mail_message_obj.create(cr, uid, {'subject': sched.name,
                                                  'type': "notification",
                                                  'partner_ids': [(6, 0, receiver_ids)],
                                                  'notified_partner_ids': [(6, 0, receiver_ids)],
                                                  'attachment_ids': [(6, 0, attachment_ids)],
                                                  'body': report_summary,
                                                  },
                                        context=context)

    def _check_overriding_values(self, cr, uid, line, values_so_far, context=None):
        return {}

    def _report_variables(self, cr, uid, line, context=None):
        result = {}
        if line.report_type == 'pentaho':
            # attempt to fill the prompt wizard as if we had gone in to it from a menu and then run.
            promptwizard_obj = self.pool.get('ir.actions.report.promptwizard')

            # default_get creates a dictionary of wizard default values
            values = promptwizard_obj.default_get_external(cr, uid, line.report_id.id, context=context)
            # this hook is provided to allow for selection set values, which are not necessarily installed
            values.update(self._check_overriding_values(cr, uid, line, values, context=context))

            if values:
                # now convert virtual screen values from prompt wizard to values which can be passed to the report action
                result = {'output_type': values.get('output_type'),
                          'variables': {}}
                parameters = json.loads(values.get('parameters_dictionary'))
                for index in range(0, len(parameters)):
                    result['variables'][parameters[index]['variable']] = promptwizard_obj.decode_wizard_value(cr, uid, parameters, index, values[parameter_resolve_column_name(parameters, index)], context=context)

        return result

    def _run_one(self, cr, uid, sched, context=None):
        if sched.line_ids or sched.user_list:
            rpt_obj = self.pool.get('ir.actions.report.xml')
            user_obj = self.pool.get('res.users')
            report_output = []
            for line in sched.line_ids:
                report = line.report_id
                service_name = "report.%s" % report.report_name
                datas = {'model': self._name,
                         }
                datas.update(self._report_variables(cr, uid, line, context=context))
#                 content, type = netsvc.LocalService(service_name).create(cr, uid, [], datas, context)
                if report.report_type in ['qweb-html', 'qweb-pdf']:
                    content, type = self.pool['report'].get_pdf(cr, uid, [], report.report_name, context=context), 'pdf'
                else:
                    content, type = openerp.report.render_report(cr, uid, [], report.report_name, datas, context)
                report_output.append((report.name, content, type))
            if report_output:
                self._send_reports(cr, uid, sched, report_output, context=context)

    def button_run_now(self, cr, uid, ids, context=None):
        for sched in self.browse(cr, uid, ids, context=context):
            self._run_one(cr, uid, sched, context=context)
        return {}

    def run_report_email_scheduler(self, cr, uid, scheduled_name='', context=None):
        for sched in self.browse(cr, uid, self.search(cr, uid, [('name', '=', scheduled_name)], context=context), context=context):
            self._run_one(cr, uid, sched, context=context)


class ReportSchedulerLines(models.Model):
    _name = "ir.actions.report.scheduler.line"
    _description = "Report Scheduler Lines"

    def check_pentaho_installed(self, cr, uid, context=None):
        return self.pool.get('ir.module.module').search(cr, uid,
                                                        [('name', '=', 'pentaho_reports'), 
                                                         ('state', 'in', ['installed', 'to upgrade', 'to remove'])
                                                         ], count=True, context=context
                                                        ) > 0

    scheduler_id = fields.Many2one('ir.actions.report.scheduler', string='Scheduler')
    report_id = fields.Many2one('ir.actions.report.xml', string='Report', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence')
    report_type = fields.Selection(string='Report Type', related='report_id.report_type', readonly=True)
    model = fields.Char(string='Object', related='report_id.model', readonly=True)
    type = fields.Char(string='Action Type', related='report_id.type', readonly=True)

    _order='sequence'
