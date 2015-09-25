# -*- coding: utf-8 -*-
{
    'name': 'Pentaho For Encrypted Passwords',
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    'website': 'http://www.willowit.com.au',
    "category": "Reporting subsystems",
    'summary':'Pentaho For Encrypted Passwords',
    'images': [],
    'depends': ['pentaho_reports', 'auth_crypt'],
    'description': """
Pentaho For Encrypted Passwords
===============================
This module provides support for Pentaho Reports where the auth_crypt (password encryption)
module has been installed.
    """,
    'data': [
            "security/ir.model.access.csv",
            ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': True,
    'application': False,
}
