# -*- coding: utf-8 -*-
{
    "name": "Pentaho Email Patch",
    "version": "1.0",
    "depends": ["pentaho_reports", "email_template"],
    "author": "Richard deMeester",
    "category": "Generic Modules/Base",
    "description": """
Resolve Pentaho reports/email concurrency issue
===============================================

This works around the OpenERP user concurrency issue when generating a Pentaho report at the same time as parsing the email template.

Creates duplicate user when spawning a Pentaho report from email templates.

This is only needed if the report being emailed is an object based report.  SQL based reports do not have this problem.
""",
    "data": [
             ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
