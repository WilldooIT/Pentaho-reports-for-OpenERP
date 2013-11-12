{
    "name": "Pentaho Custom Data Sample",
    "version": "1.0",
    "depends": [
        "base", 
        "pentaho_reports",
    ],
    "author": "Doug Parker - Willow IT",
    "category": "Sample",
    "description": """
Pentaho Custom Data Sample
==========================

Uses the Custom Data Function with the OpenERP Data Access data source in a Pentaho Report.

The Custom Data Function calls a method on the OpenERP model to retrieve its data.
The method can construct the report data in any way it chooses and is not restricted to returning rows from OpenERP models. 

Two reports are added by this module. They both produce a simple list of partner names but use custom data methods to do it. 

* 'Pentaho ids Custom Data Example': Run this report by displaying a list of partners (customers or suppliers), selecting one or more then choosing the report from the 'Print' menu. The list of ids of selected partners is automatically passed to the report by the pentaho_reports module. The custom data method receives the list of ids and returns the names of the selected partners.

* 'Pentaho params Custom Data Example': Run this report from the menu item that appears under the Sales / Sales menu. The pentaho_reports module automatically displays a wizard prompting the user for the report 'Name' parameter. The custom data method receives this paramter and returns the names of partners matching it using the 'ilike' comparison.  
""",
    'data': [
        'reports.xml',
    ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
