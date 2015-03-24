# -*- encoding: utf-8 -*-

# As code is written in the new_api structure, it should go in here and be removed from core.py

from openerp import models, fields, api, _
from openerp.exceptions import except_orm

from openerp import sql_db

PENTAHO_TEMP_USER_PW = 'TempPWPentaho'
PENTAHO_TEMP_USER_LOGIN = '%s (Pentaho)'

class res_users(models.Model):
    _inherit = 'res.users'

    #Fudge to fix bad base code....
    def _create_welcome_message(self, cr, uid, user, context=None):
        if context is None:
            context = {}
        if context.get('dont_welcome'):
            return False
        super(res_users, self)._create_welcome_message(cr, uid, user, context=context)

    @api.multi
    def pentaho_temp_user_find(self):
        self.ensure_one()
        user = self.sudo().browse(self.id)
        temp_users = self.sudo().search([('login', '=', PENTAHO_TEMP_USER_LOGIN % user.login)])
        if not temp_users:
            self.pentaho_temp_user_create()
        return PENTAHO_TEMP_USER_LOGIN % user.login

    @api.multi
    def pentaho_temp_user_create(self):
        self.ensure_one()
        self.pentaho_temp_users_unlink()
        with api.Environment.manage():
            new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
            new_env = self.env(new_cr, self.env.uid, {'no_reset_password': True,
                                                      'tracking_disable': True,
                                                      'dont_welcome': True,
                                                      'skip_cleanup': True,
                                                      })
            user = self.with_env(new_env).sudo().browse(self.id)
#             new_user = self.with_env(new_env).sudo().copy(default={'login': PENTAHO_TEMP_USER_LOGIN % user.login,
#                                                                    'password': PENTAHO_TEMP_USER_PW,
#                                                                    'user_ids': False,
#                                                                    'message_ids': False,
#                                                                    'name': user.name,
#                                                                    })
            #
            # This next bit of code is awful.  BUT, writing a value to groups_id has an explicit "invalidate_cache".  This
            # nasty generally has no impact on the overall scheme of things, BUT, when the pentaho report is called from
            # on change in the mail compose wizard, the invalidate cache causes the on screen wizard to be invalidated!!!!
            #
            # This specific insert of securities ensures we don't end up in that rabbit hole
            #
            new_user = self.with_env(new_env).sudo().create({'login': PENTAHO_TEMP_USER_LOGIN % user.login,
                                                             'password': PENTAHO_TEMP_USER_PW,
                                                             'user_ids': False,
                                                             'message_ids': False,
                                                             'name': user.name,
                                                             'groups_id': False,
                                                             'signature': user.signature,
                                                             'title': user.title,
                                                             'lang': user.lang,
                                                             'tz': user.tz,
                                                             })
            for g in user.groups_id.ids:
                if not g in new_user.groups_id.ids:
                    new_cr.execute("""INSERT INTO res_groups_users_rel
                                        (uid, gid) VALUES
                                        (%s, %s);""", (new_user.id, g))
            new_cr.commit()
            new_cr.close()
        return new_user.id

    @api.multi
    def pentaho_temp_users_unlink(self):
        with api.Environment.manage():
            new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
            new_env = self.env(new_cr, self.env.uid, {})
            self.with_env(new_env)._pentaho_temp_users_unlink()
            new_cr.commit()
            new_cr.close()

    @api.multi
    def _pentaho_temp_users_unlink(self):
        """Unlink users and associated partners.
        """
        existing_users = self.sudo().browse()
        existing_partners = self.sudo().env['res.partner']
        #
        # We may be here during "create", but we are in a separate transaction, so the passed 'id' may not have been written and known about the self record yet...
        #
        for user in self.sudo().search([('id', 'in', self.ids)]):
            existing_users += self.sudo().search([('login', '=', PENTAHO_TEMP_USER_LOGIN % user.login)])
        for user in existing_users:
            if user.partner_id:
                existing_partners += user.partner_id

#         existing_users.unlink()
#         existing_partners.unlink()
        if existing_users:
            #
            # Again, caching issues in base odoo bite us, so remove records manually...
            #
            if 1 in existing_users.ids:
                existing_users = existing_users - self.sudo().browse(1)
            self.env.cr.execute("""DELETE FROM res_users WHERE id IN %s;""", (tuple(existing_users.ids),))
        if existing_partners:
            #
            # Again, caching issues in base odoo bite us, so remove records manually...
            #
            self.env.cr.execute("""DELETE FROM res_partner WHERE id IN %s;""", (tuple(existing_partners.ids),))

    @api.multi
    def write(self, values):
        #
        # Crude clean-up code - if something writes to res_users then assume it is OK to clean up temp users...
        #
        if not self.env.context.get('skip_cleanup'):
            self.pentaho_temp_users_unlink()
        return super(res_users, self).write(values)
