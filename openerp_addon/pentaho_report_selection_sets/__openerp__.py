# -*- encoding: utf-8 -*-
{
    "name": "Pentaho Report Selections Saving",
    "description": """
Pentaho - Report Selections Saving
==================================
This module builds on the OpenERP Pentaho Report functionality by allowing report selections to be stored and
retrieved.  Those selections can have a dynamic element by using selection default functions.

To be able to store and maintain selection sets, a user must have their security set accordingly.

    """,
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    "website": "http://www.willowit.com.au/",
    "depends": ["pentaho_reports"],
    "category": "Reporting subsystems",
    "data": [
             "security/pentaho_selection_set_security.xml",
             "security/ir.model.access.csv",
             "wizard/store_selections.xml",
             "report_prompt.xml",
             ],
    "installable": True,
    "active": False
}
