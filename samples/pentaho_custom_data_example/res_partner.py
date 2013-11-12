from openerp.osv import fields, osv


class res_partner(osv.osv):
    _inherit = 'res.partner'


    def report_custom_data_params(self, cr, uid, *param):
        """Custom data method for 'params' report. 
        
        'param' is a tuple where the first element is a dict with
        any report parameters (keyed by the parameter name) and
        other environmental info.

        In this example the report has a single defined parameter
        'p_name' which is a string. The code below uses 'ilike'
        to select partners matching the name.
        
        The pentaho_report module will automatically prompt the user
        for report parameters via a wizard when the report is run
        from a menu. See reports.xml in this module.
        """

#       Comment-in the line below to see the params passed
#       from Pentaho to this method.
#       print("***DEBUG PARAMS PARAMS: |%s|" % param)

        param = param[0]

        # If getFields is true then return dict of field names
        # in the result set of this method.
        if param.get('getFields'):
            return [{
                'name': {'type': 'string'},
            }]

        # Retrieve the data
        search_args = []
        p_name = param.get('p_name')
        if p_name:
            search_args.extend([('name', 'ilike', p_name)])
        
        ids = self.search(cr, uid, search_args)

        # Build the result
        result = []
        for partner in self.browse(cr, uid, ids):
            result.append({
                'name': partner.name or False,
            })

        return result


    def report_custom_data_ids(self, cr, uid, *param):
        """Custom data method for 'ids' report. 

        'param' is a tuple where the first element is a dict with
        any report parameters (keyed by the parameter name) and
        other environmental info.

        In this example the report has a single defined parameter
        'ids' which is a list of integers.

        The 'ids' parameter will be automatically populated by the
        pentaho_reports module when the report is associated with
        the res.partner model and the report is run via the
        partners 'Print' menu. See reports.xml in this module.
        """

#       Comment-in the line below to see the params passed
#       from Pentaho to this method.
#       print("***DEBUG IDS PARAMS: |%s|" % param)

        param = param[0]

        # If getFields is true then return dict of field names
        # in the result set of this method.
        if param.get('getFields'):
            return [{
                'name': {'type': 'string'},
            }]

        # Get passed ids
        ids = param.get('ids', [])

        # Build the result
        result = []
        for partner in self.browse(cr, uid, ids):
            result.append({
                'name': partner.name or False,
            })

        return result
