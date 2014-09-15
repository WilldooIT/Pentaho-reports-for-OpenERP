import base64
import pooler
import netsvc
from osv import osv, fields
import tools
from openerp import SUPERUSER_ID


class email_template_patch(osv.osv):
    _inherit = 'email.template'


    def _unlink_user_and_partner(self, cr, uid, user_ids, context=None):
        """Unlink a user and its associated partner.
        This is used to remove the temporary user/partner created by the patch in generate_email().
        """
        user_obj = self.pool.get('res.users')
        for this_user in user_obj.browse(cr, uid, user_ids, context=context):
            partner_id = this_user.partner_id and this_user.partner_id.id or False
            user_obj.unlink(cr, SUPERUSER_ID, [this_user.id], context=context)
            if partner_id:
                self.pool.get('res.partner').unlink(cr, uid, [partner_id], context=context)


    def generate_email(self, cr, uid, template_id, res_id, context=None):
        """This is a copy of generate_email from email.template, with a patch as below.
        """
        if context is None:
            context = {}
        report_xml_pool = self.pool.get('ir.actions.report.xml')
        template = self.get_email_template(cr, uid, template_id, res_id, context)
        values = {}
        for field in ['subject', 'body_html', 'email_from',
                      'email_to', 'email_recipients', 'email_cc', 'reply_to']:
            values[field] = self.render_template(cr, uid, getattr(template, field),
                                                 template.model, res_id, context=context) \
                                                 or False
        if template.user_signature:
            signature = self.pool.get('res.users').browse(cr, uid, uid, context).signature
            values['body_html'] = tools.append_content_to_html(values['body_html'], signature)

        if values['body_html']:
            values['body'] = tools.html_sanitize(values['body_html'])

        values.update(mail_server_id=template.mail_server_id.id or False,
                      auto_delete=template.auto_delete,
                      model=template.model,
                      res_id=res_id or False)

        attachments = []
        # Add report in attachments
        if template.report_template:
            report_name = self.render_template(cr, uid, template.report_name, template.model, res_id, context=context)
            report_service = 'report.' + report_xml_pool.browse(cr, uid, template.report_template.id, context).report_name
            # Ensure report is rendered using template's language
            ctx = context.copy()
            if template.lang:
                ctx['lang'] = self.render_template(cr, uid, template.lang, template.model, res_id, context)

            # Start of Patch.

#           service = netsvc.LocalService(report_service)
#           (result, format) = service.create(cr, uid, [res_id], {'model': template.model}, ctx)

            if not report_xml_pool.browse(cr, uid, template.report_template.id, context).is_pentaho_report:
                # Standard service call for non-Pentaho reports
                service = netsvc.LocalService(report_service)
                (result, format) = service.create(cr, uid, [res_id], {'model': template.model}, ctx)
            else:
                # Call the report as a duplicate of the current user to remove the user concurrency issue.
                # NOTE: This works HOWEVER, if the temp user is in the in the 'portal' or 'anonymous' security groups
                #       then rendering the Pentaho report may fail because the user is denied read access to res.partner.
                #       See security rule 'res_partner: read access on my partner'.
                crtemp = pooler.get_db(cr.dbname).cursor()

                #Remove default_partner_id set by search view that could duplicate user with existing partner!
                # Use copied context, to ensure we don't affect any processing outside of this method's scope.
                ctx.pop('default_partner_id', None)

                user_obj = self.pool.get('res.users')
                existing_uids = user_obj.search(crtemp, SUPERUSER_ID, [('login', '=', "%s (copy)" % user_obj.browse(crtemp, SUPERUSER_ID, uid, context=ctx).login)], context=ctx)
                if existing_uids:
                    self._unlink_user_and_partner(crtemp, uid, existing_uids, context=ctx)

                new_uid = user_obj.copy(crtemp, SUPERUSER_ID, uid, default={'employee_ids': False, 'message_ids': False}, context=ctx)
                crtemp.commit()

                service = netsvc.LocalService(report_service)
                (result, format) = service.create(crtemp, new_uid, [res_id], {'model': template.model}, ctx)
                crtemp.commit()
                crtemp.close()

                crtemp = pooler.get_db(cr.dbname).cursor()

                self._unlink_user_and_partner(crtemp, uid, [new_uid], context=ctx)

                crtemp.commit()
                crtemp.close()

            # End of Patch

            result = base64.b64encode(result)
            if not report_name:
                report_name = report_service
            ext = "." + format
            if not report_name.endswith(ext):
                report_name += ext
            attachments.append((report_name, result))

        # Add template attachments
        for attach in template.attachment_ids:
            attachments.append((attach.datas_fname, attach.datas))

        values['attachments'] = attachments
        return values
