# -*- encoding: utf-8 -*-

# As code is written in the new_api structure, it should go in here and be removed from core.py

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, AccessDenied

from openerp import sql_db, SUPERUSER_ID

SKIP_DATE = 'SKIP_DATE_RECORDING'

import logging
_logger = logging.getLogger(__name__)

class res_users(models.Model):
    _inherit = 'res.users'

    @api.multi
    def pentaho_pass_token(self):
        return '%s%s' % (SKIP_DATE, self.decide_on_password())

    @api.multi
    def pentaho_undo_token(self, token):
        if token[0:len(SKIP_DATE)] == SKIP_DATE:
            self.reverse_password(token.replace(SKIP_DATE, ''))

    def decide_on_password(self):
        return self.sudo().password

    def reverse_password(self, password):
        pass

    @api.model
    def strip_password(self, password):
        if password[0:len(SKIP_DATE)] == SKIP_DATE:
            password = password.replace(SKIP_DATE, '')
        return password

    def check_credentials(self, cr, uid, password):
        password = self.strip_password(cr, uid, password)
        return super(res_users, self).check_credentials(cr, uid, password)

    def _login(self, db, login, password):
        if not password:
            return False
        if password == SKIP_DATE:
            _logger.error('*** Install pentaho_reports_auth_crypt to run with encrypted passwords. ***')
            return False
        user_id = False
        cr = self.pool.cursor()
        try:
            # autocommit: our single update request will be performed atomically.
            # (In this way, there is no opportunity to have two transactions
            # interleaving their cr.execute()..cr.commit() calls and have one
            # of them rolled back due to a concurrent access.)
            cr.autocommit(True)
            # check if user exists
            res = self.search(cr, SUPERUSER_ID, [('login','=',login)])
            if res:
                user_id = res[0]

                if password[0:len(SKIP_DATE)] == SKIP_DATE:
                    skip_date_recording = True
                else:
                    skip_date_recording = False

                # check credentials
                self.check_credentials(cr, user_id, password)

                # We effectively unconditionally write the res_users line.
                # Even w/ autocommit there's a chance the user row will be locked,
                # in which case we can't delay the login just for the purpose of
                # update the last login date - hence we use FOR UPDATE NOWAIT to
                # try to get the lock - fail-fast
                # Failing to acquire the lock on the res_users row probably means
                # another request is holding it. No big deal, we don't want to
                # prevent/delay login in that case. It will also have been logged
                # as a SQL error, if anyone cares.
                try:
                    if not skip_date_recording:
                        # NO KEY introduced in PostgreSQL 9.3 http://www.postgresql.org/docs/9.3/static/release-9-3.html#AEN115299
                        update_clause = 'NO KEY UPDATE' if cr._cnx.server_version >= 90300 else 'UPDATE'
                        cr.execute("SELECT id FROM res_users WHERE id=%%s FOR %s NOWAIT" % update_clause, (user_id,), log_exceptions=False)
                        cr.execute("UPDATE res_users SET login_date = now() AT TIME ZONE 'UTC' WHERE id=%s", (user_id,))
                        self.invalidate_cache(cr, user_id, ['login_date'], [user_id])
                except Exception:
                    _logger.debug("Failed to update last_login for db:%s login:%s", db, login, exc_info=True)
        except AccessDenied:
            _logger.info("Login failed for db:%s login:%s", db, login)
            user_id = False
        finally:
            cr.close()

        return user_id
