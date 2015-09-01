from openerp import models, fields, api, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import openerp
from datetime import datetime, timedelta
import random, string

class PentahoAuthCrypt(models.Model):
    _name = 'pentaho.auth.crypt'
    _description = 'Pentah Auth Crypt'

    user_id = fields.Many2one('res.users')
    value = fields.Char()
    timestamp = fields.Datetime()

class ResUsersPentahoCrypt(models.Model):
    _inherit = "res.users"

    def decide_on_password(self):
        # If we could determine if the report needs to call back, we could make this step optional and not execute every time...
        return self.create_temporary_password_pentaho()

    def reverse_password(self, password):
        self.remove_temporary_password_pentaho(password)

    def create_temporary_password_pentaho(self):
        new_cr = openerp.registry(self.env.cr.dbname).cursor()
        pword = ''.join(random.choice(string.ascii_letters + string.digits + '!@#$%^&*()') for x in range(64))

        env = api.Environment(new_cr, self.env.uid, self.env.context)
        env['pentaho.auth.crypt'].create({'user_id': self.env.uid,
                                          'value': pword,
                                          'timestamp': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                          })
        new_cr.commit()
        new_cr.close()
        return pword

    def check_credentials(self, cr, uid, password):
        password = self.strip_password(cr, uid, password)
        cr.execute ('SELECT id FROM pentaho_auth_crypt WHERE user_id=%s AND value=%s', (uid, password))
        if cr.rowcount:
            return
        return super(ResUsersPentahoCrypt, self).check_credentials(cr, uid, password)

    def remove_temporary_password_pentaho(self, value):
        new_cr = openerp.registry(self.env.cr.dbname).cursor()
        env = api.Environment(new_cr, self.env.uid, self.env.context)
        # also get rid of tokens that are over 24 hours old...
        recs = env['pentaho.auth.crypt'].search(['|', '&',
                                                 ('user_id', '=', self.env.uid),
                                                 ('value', '=', value),
                                                 ('timestamp', '<=', (datetime.now() - timedelta(hours=24)).strftime(DEFAULT_SERVER_DATETIME_FORMAT))
                                                 ])
        recs.unlink()
        new_cr.commit()
        new_cr.close()
