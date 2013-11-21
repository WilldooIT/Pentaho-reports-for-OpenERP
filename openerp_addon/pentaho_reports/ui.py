# -*- encoding: utf-8 -*-

import os
import base64
from openerp.tools.translate import _
from openerp.tools.safe_eval import safe_eval
from openerp.osv import orm, fields
from openerp.tools import config

from openerp import SUPERUSER_ID

import core

from java_oe import JAVA_MAPPING, check_java_list, PARAM_VALUES

ADDONS_PATHS = config['addons_path'].split(",")


class report_xml(orm.Model):
    _inherit = 'ir.actions.report.xml'
    _columns = {
                'pentaho_report_output_type': fields.selection([("pdf", "PDF"), ("html", "HTML"), ("csv", "CSV"), ("xls", "Excel"), ("rtf", "RTF"), ("txt", "Plain text")],
                                                               'Output format'),
                'pentaho_report_model_id': fields.many2one('ir.model', 'Model'),
                'pentaho_file': fields.binary('File', filters='*.prpt'),
                'pentaho_filename': fields.char('Filename', size=256, required=False),
                'is_pentaho_report': fields.boolean('Is this a Pentaho report?'),
                'linked_menu_id': fields.many2one('ir.ui.menu', 'Linked menu item', select=True),
                'created_menu_id': fields.many2one('ir.ui.menu', 'Created menu item'),
                # This is not displayed on the client - it is a trigger to indicate that
                # a prpt file needs to be loaded - normally it is loaded by the client interface
                # In this case, the filename should be specified with a module path.
                'pentaho_load_file': fields.boolean('Load prpt file from filename'),
                }

    def onchange_is_pentaho(self, cr, uid, ids, is_pentaho_report, context=None):
        result = {'value': {}}
        if is_pentaho_report:
            result['value'].update({'auto' : False,
                                    'pentaho_report_output_type': 'pdf'
                                    })
        return result

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default = default.copy()
        default.update({'created_menu_id': 0})
        return super(report_xml, self).copy(cr, uid, id, default, context=context)

    def create_menu(self, cr, uid, vals, context=None):
        view_ids = self.pool.get('ir.ui.view').search(cr, uid, [('model', '=', 'ir.actions.report.promptwizard'), ('type', '=', 'form')], context=context)

        action_vals = {'name': vals.get('name', 'Pentaho Report'),
                       'res_model': 'ir.actions.report.promptwizard',
                       'type' : 'ir.actions.act_window',
                       'view_type': 'form',
                       'view_mode': 'tree,form',
                       'view_id' : view_ids and view_ids[0] or 0,
                       'context' : "{'service_name': '%s'}" % vals.get('report_name', ''),
                       'target' : 'new',
                       }
        action_id = self.pool.get('ir.actions.act_window').create(cr, uid, action_vals, context=context)

        result = self.pool.get('ir.ui.menu').create(cr, SUPERUSER_ID, {
                                                                       'name': vals.get('name' ,'Pentaho Report'),
                                                                       'sequence': 10,
                                                                       'parent_id': vals['linked_menu_id'],
                                                                       'groups_id': vals.get('groups_id', []),
                                                                       'icon': 'STOCK_PRINT',
                                                                       'action': 'ir.actions.act_window,%d' % (action_id,),
                                                                       }, context=context)

        return result

    def delete_menu(self, cr, uid, menu_id, context=None):
        action = self.pool.get('ir.ui.menu').browse(cr, uid, menu_id, context=context).action
        if action and action._model._name == 'ir.actions.act_window':
            self.pool.get('ir.actions.act_window').unlink(cr, uid, [action.id], context=context)
        result = self.pool.get('ir.ui.menu').unlink(cr, SUPERUSER_ID, [menu_id], context=context)
        return result

    def update_menu(self, cr, uid, action_report, context=None):
        if action_report.created_menu_id and not action_report.linked_menu_id:
            self.delete_menu(cr, uid, action_report.created_menu_id.id, context=context)

        if action_report.is_pentaho_report and action_report.linked_menu_id:
            groups_id = [(6, 0, map(lambda x: x.id, action_report.groups_id))]
            if not action_report.created_menu_id:
                result = self.create_menu(cr, uid, {'name': action_report.name,
                                                    'linked_menu_id': action_report.linked_menu_id.id,
                                                    'report_name': action_report.report_name,
                                                    'groups_id': groups_id,
                                                    }, context=context)
            else:
                action = action_report.created_menu_id.action
                if action and action._model._name == 'ir.actions.act_window':
                    existing_context = safe_eval(self.pool.get('ir.actions.act_window').browse(cr, uid, action.id, context=context).context)
                    new_context = existing_context if type(existing_context) == dict else {}
                    new_context['service_name'] = action_report.report_name or ''
                    self.pool.get('ir.actions.act_window').write(cr, uid, [action.id], {'name': action_report.name or 'Pentaho Report',
                                                                                        'context': str(new_context),
                                                                                        }, context=context)

                self.pool.get('ir.ui.menu').write(cr, SUPERUSER_ID, [action_report.created_menu_id.id], {'name': action_report.name or 'Pentaho Report',
                                                                                                         'parent_id': action_report.linked_menu_id.id,
                                                                                                         'groups_id': groups_id,
                                                                                                         }, context=context)
                result = action_report.created_menu_id.id
        else:
            result = 0

        return result

    def create(self, cr, uid, vals, context = None):
        if vals.get('is_pentaho_report'):
            vals.update({
                         'model': self.pool.get('ir.model').browse(cr, uid, vals['pentaho_report_model_id'], context=context).model,
                         'type': 'ir.actions.report.xml',
                         'report_type': 'pdf',
                         'auto': False,
                         })

            if vals.get('linked_menu_id', False):
                vals['created_menu_id'] = self.create_menu(cr, uid, vals, context=context)

        res = super(report_xml, self).create(cr, uid, vals, context=context)
        self.update_pentaho(cr, uid, [res], context=context)
        return res

    def write(self, cr, uid, ids, vals, context = None):
        if vals.get('is_pentaho_report'):
            if 'pentaho_report_model_id' in vals:
                vals['model'] = self.pool.get('ir.model').browse(cr, uid, vals['pentaho_report_model_id'], context=context).model
            vals.update({
                         'type': 'ir.actions.report.xml',
                         'report_type': 'pdf',
                         'auto': False,
                         })

        res = super(report_xml, self).write(cr, uid, ids, vals, context=context)

        for r in self.browse(cr, uid, ids if isinstance(ids, list) else [ids], context=context):
            created_menu_id = self.update_menu(cr, uid, r, context=context)
            if created_menu_id != r.created_menu_id:
                super(report_xml, self).write(cr, uid, [r.id], {'created_menu_id': created_menu_id}, context=context)

        self.update_pentaho(cr, uid, ids if isinstance(ids, list) else [ids], context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        values_obj = self.pool.get('ir.values')

        for r in self.browse(cr, uid, ids, context=context):
            if r.created_menu_id:
                self.delete_menu(cr, uid, r.created_menu_id.id, context=context)
            values_obj.unlink(cr, SUPERUSER_ID, values_obj.search(cr, uid, [('value', '=', 'ir.actions.report.xml,%s' % r.id)]), context=context)

        return super(report_xml, self).unlink(cr, uid, ids, context=context)

    def update_pentaho(self, cr, uid, ids, context = None):
        values_obj = self.pool.get('ir.values')

        for report in self.browse(cr, uid, ids):
            values_ids = values_obj.search(cr, uid, [('value', '=', 'ir.actions.report.xml,%s' % report.id)])

            if report.is_pentaho_report:
                if report.pentaho_filename:
                    if report.pentaho_load_file:
                        # if we receive a filename and no content, this has probably been loaded by a process other than the standard client, such as a data import
                        # in this case, we expect the filename to be a fully specified file within a module from which we load the file data
                        super(report_xml, self).write(cr, uid, [report.id], {'pentaho_filename': os.path.basename(report.pentaho_filename),
                                                                             'pentaho_file': self.read_content_from_file(report.pentaho_filename),
                                                                             'pentaho_load_file': False
                                                                             })
                        report = self.browse(cr, uid, report.id)

#                    path = self.save_content_to_file(report.pentaho_filename, report.pentaho_file)
#                    super(report_xml, self).write(cr, uid, [report.id], {'report_rml': path})

                    # we are no longer relying on report_rml to contain a name at all - for clarity, though, still store it...
                    super(report_xml, self).write(cr, uid, [report.id], {'report_rml': report.pentaho_filename})

                    if not report.linked_menu_id and report.pentaho_filename.endswith('.prpt'):
                        data = {
                                'name': report.name,
                                'model': report.model,
                                'key': 'action',
                                'object': True,
                                'key2': 'client_print_multi',
                                'value': 'ir.actions.report.xml,%s' % report.id,
                                }
                        if not values_ids:
                            values_obj.create(cr, SUPERUSER_ID, data, context=context)
                        else:
                            values_obj.write(cr, SUPERUSER_ID, values_ids, data, context=context)
                        values_ids = []
                    core.register_pentaho_report(report.report_name)

                elif report.pentaho_file:
                    super(report_xml, self).write(cr, uid, [report.id], {'pentaho_file': False})

                # If this is a pentaho report and there are still "values_ids", it means that
                # the action is not considered valid - get rid of the values_ids...
                if values_ids:
                    values_obj.unlink(cr, SUPERUSER_ID, values_ids, context=context)

            # If this is not a pentaho report, then the action should always have a row in values
            else:
                if not values_ids:
                    values_obj.create(cr, SUPERUSER_ID, {
                                                         'name': report.name,
                                                         'model': report.model,
                                                         'key': 'action',
                                                         'object': True,
                                                         'key2': 'client_print_multi',
                                                         'value': 'ir.actions.report.xml,%s' % report.id,
                                                         },
                                      context = context)
        return True

    def read_content_from_file(self, name):
        path_found = False
        for addons_path in ADDONS_PATHS:
            try:
                os.stat(addons_path + os.sep + name)
                path_found = True
                break
            except:
                pass

        if not path_found:
            raise orm.except_orm(_('Error'), _('Could not locate path for file %s') % name)

        path = addons_path + os.sep + name

        with open(path, "rb") as report_file:
            data = base64.encodestring(report_file.read())

        return data


    def pentaho_validate_params(self, cr, uid, report, param_vals, context=None):
        """Validate a list of passed parameters against the defined params for
        a Pentaho report.

        Raises an exception if any of the params are invalid.

        @param report: Browse object on the ir.actions.report.xml record for the report.
        @param param_vals: Dict with parameter values to pass to the report. These are python 
            data types prior to conversion for passing to the Pentaho server.
        """
        param_defs = core.fetch_report_parameters(cr, uid, report.report_name, context=context)

        val_names = param_vals.keys()
        for pdef in param_defs:
            pname = pdef.get('name', '')
            if not pname:
                continue

            if pname in val_names:
                val_names.remove(pname)
            else:
                if pdef.get('default_value', False):
                    if type(pdef['default_value']) in (list, tuple):
                        param_vals[pname] = pdef['default_value'][0]
                    else:
                        param_vals[pname] = pdef['default_value']
                else:
                    if pdef.get('is_mandatory', False):
                        raise orm.except_orm(_('Error'), _("Report '%s'. No value passed for mandatory report parameter '%s'.") % (report.report_name, pname))
                    continue

            # Make sure data types match
            value_type = pdef.get('value_type', '')
            java_list, value_type = check_java_list(value_type)
            if not value_type in JAVA_MAPPING:
                raise orm.except_orm(_('Error'), _("Report '%s', parameter '%s'. Type '%s' not supported.") % (report.report_name, pname, pdef.get('value_type', '')))

            local_type = JAVA_MAPPING[value_type](pdef.get('attributes', {}).get('data-format', False))

            param_val = param_vals[pname]

            if not local_type in PARAM_VALUES:
                raise orm.except_orm(_('Error'), _("Report '%s', parameter '%s'. Local type '%s' not supported.") % (report.report_name, pname, local_type))
            if not isinstance(param_val, PARAM_VALUES[local_type]['py_types']):
                raise orm.except_orm(_('Error'), _("Report '%s', parameter '%s'. Passed value is '%s' but must be one of '%s'.") % (report.report_name, pname, param_val.__class__.__name__, PARAM_VALUES[local_type]['py_types']))

            converter = PARAM_VALUES[local_type].get('convert')
            if converter:
                try:
                    converter(param_val)
                except Exception, e:
                    raise orm.except_orm(_('Error'), _("Report '%s', parameter '%s'. Passed value '%s' failed data conversion to type '%s'.\n%s") % (report.report_name, pname, param_val, local_type, str(e)))


        # Make sure all passed values have a param to go to on the report.
        # This wouldn't raise an error on the Pentaho side but flagging it here
        # might save a lot of development time if a param is misnamed.
        if val_names:
            raise orm.except_orm(_('Error'), _("Report '%s'. Parameter values not required by report: %s") % (report.report_name, val_names))

    def pentaho_report_action(self, cr, uid, service_name, active_ids=None, param_values=None, context=None):
        """Return the action definition to run a Pentaho report.

        The action definition is returned as a dict which can be returned
        to the OpenERP client from a wizard button or server action to
        cause the client to request the report.

        @param service_name: The report service name (without leading 'report.').
        @param active_ids: List of ids on the report model to pass.
        @param param_values: Dict with parameter values for the report.
            The keys are the parameter names as defined by the Pentaho report.
        """
        report = False
        report_ids = self.search(cr, uid, [('report_name', '=', service_name)], context=context)
        if report_ids:
            report = self.browse(cr, uid, report_ids[0], context=context)
        if (not report) or (not report.is_pentaho_report):
            raise orm.except_orm(_('Error'), _("Report '%s' is not a Pentaho report.") % service_name)

        if (not active_ids) and (not param_values):
            raise orm.except_orm(_('Error'), _("Report '%s' must be passed active ids or parameter values.") % service_name)

        datas = {'model': report.model,
                 'output_type': report.report_type,
                }

        if active_ids:
            datas['ids'] = active_ids

        if param_values:
            self.pentaho_validate_params(cr, uid, report, param_values, context=context)
            datas['variables'] = param_values
        return {
                'type': 'ir.actions.report.xml',
                'report_name': report.report_name,
                'datas': datas,
                }
