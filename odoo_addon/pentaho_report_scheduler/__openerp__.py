# -*- coding: utf-8 -*-
{
    'name': 'Report Scheduler',
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    'website': 'http://www.willowit.com.au',
    "category": "Reporting subsystems",
    'summary':'Report Scheduler',
    'images': [],
    'depends': ['base'],
    'description': """
Report Email / Message Scheduler
================================
This module provides a simple scheduler running daily reports. The reports may not accept any parameters.

The module "Report Scheduler Selection Sets" (pentaho_report_scheduler_selection_sets) module extends this module
and allows Pentaho reports to be scheduled with pre-entered selections.

Chosen reports can be either emailed to users or sent to their OpenERP message box as a notification, or both.

A new option is added to the menus:
    * **Settings / Technical / Actions / Scheduler / Report Scheduler**

From here, a report schedule group can be defined.  The description will be included in the message or email body.

Once defined, the schedule group needs to be associated with a standard OpenERP schedule task.  (An example
schedule task is created by this module, and is titled **Report Email Scheduler**). On the **Technical Data** tab,
the name of the schedule group needs to be included in the action argument.

e.g. *('Report Group 1',)*

Note the **comma** after the argument **IS** required.
    """,
    'data': [
             'scheduler.xml',
             'scheduler_view.xml',
             'security/ir.model.access.csv',
            ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
