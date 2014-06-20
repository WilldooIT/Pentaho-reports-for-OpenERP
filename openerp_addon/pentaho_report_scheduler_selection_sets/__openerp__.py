# -*- coding: utf-8 -*-
{
    'name': 'Report Scheduler Selection Sets',
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    'website': 'http://www.willowit.com.au',
    "category": "Reporting subsystems",
    'summary':'Report Scheduler with Selection Sets',
    'images': [],
    'depends': ['pentaho_report_selection_sets',
                'pentaho_report_scheduler',
                ],
    'description': """
Report Scheduler with Selection Sets
====================================
This module provides extends the report scheduler and allows the scheduling of Pentaho reports that have
pre-defined selection sets.

The desired selection set to be used needs to be chosen in the report schedule group.
    """,
    'data': [
             'scheduler_view.xml',
            ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
