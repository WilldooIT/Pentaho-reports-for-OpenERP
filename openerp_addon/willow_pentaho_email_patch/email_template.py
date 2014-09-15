import base64
from openerp import netsvc
from openerp import pooler
from openerp import models, fields
from openerp import tools
from openerp import SUPERUSER_ID
import openerp


class email_template_patch(models.Model):
    _inherit = 'email.template'

    def generate_email_batch(self, cr, uid, template_id, res_ids, context=None, fields=None):
        if context is None:
            context = {}
        context['pentaho_report_email_patch'] = True
        return super(email_template_patch, self).generate_email_batch(cr, uid, template_id, res_ids, context=context, fields=fields)

class ir_actions_report_xml_patch(models.Model):

    _inherit = 'ir.actions.report.xml'

    def _unlink_user_and_partner(self, cr, uid, user_ids, context=None):
        """Unlink a user and its associated partner.
        """
        user_obj = self.pool.get('res.users')
        for this_user in user_obj.browse(cr, uid, user_ids, context=context):
            partner_id = this_user.partner_id and this_user.partner_id.id or False
            user_obj.unlink(cr, SUPERUSER_ID, [this_user.id], context=context)
            if partner_id:
                self.pool.get('res.partner').unlink(cr, uid, [partner_id], context=context)


    def render_report(self, cr, uid, res_ids, name, data, context=None):

        standard_render = True
        if context.get('pentaho_report_email_patch'):

            # This patch is needed if the report is a Pentaho report, and that Pentaho report is an object
            # based report, because Pentaho will log in as the passed user.

            # If we are here, then we have not checked if it is a Pentaho report, let along if it is object based.
            # However, this code does not hurt to be executed in any case, so we do not check those conditions
            # explicitly.

            standard_render = False

            crtemp = pooler.get_db(cr.dbname).cursor()
            #Remove default_partner_id set by some search views that could duplicate user with existing partner!
            # Use copied context, to ensure we don't affect any processing outside of this method's scope.
            ctx = (context or {}).copy()
            ctx.pop('default_partner_id', None)
            ctx['no_reset_password'] = True

            user_obj = self.pool.get('res.users')
            user = user_obj.browse(crtemp, SUPERUSER_ID, uid, context=ctx)
            existing_uids = user_obj.search(crtemp, SUPERUSER_ID, [('login', '=', "%s (copy)" % user.login)], context=ctx)
            if existing_uids:
                self._unlink_user_and_partner(crtemp, uid, existing_uids, context=ctx)

            new_uid = user_obj.copy(crtemp, SUPERUSER_ID, uid, default={'password': user.password, 'user_ids': False}, context=ctx)
            crtemp.commit()

            result = super(ir_actions_report_xml_patch, self).render_report(crtemp, new_uid, res_ids, name, data, context=context)
            crtemp.commit()
            crtemp.close()

            crtemp = pooler.get_db(cr.dbname).cursor()
            self._unlink_user_and_partner(crtemp, uid, [new_uid], context=ctx)
            crtemp.commit()
            crtemp.close()

        if standard_render:
            result = super(ir_actions_report_xml_patch, self).render_report(cr, uid, res_ids, name, data, context=context)

        return result
