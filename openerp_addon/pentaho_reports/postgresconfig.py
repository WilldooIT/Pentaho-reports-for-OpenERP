from osv import fields, osv


#---------------------------------------------------------------------------------------------------------------

class PostgresConfig(osv.osv):

    _name = 'pentaho.postgres.config'

    _columns = {
                'name' : fields.char('Configuration', 64, required=True),
                "host" : fields.char('Postgres Host', 64),
                "port": fields.char('Postgres Port',10),
                "login": fields.char('Postgres Login', 64, required=True),
                "password": fields.char('Postgres Password', 64, required=True),
                }


PostgresConfig()
