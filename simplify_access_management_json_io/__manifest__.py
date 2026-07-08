# -*- coding: utf-8 -*-
{
    'name': 'Simplify Access Management JSON Import/Export',
    'version': '16.0.1.0.0',
    'summary': 'Export and import Simplify Access Management rules using portable JSON',
    'category': 'Tools',
    'author': 'ODOO VERSION 16/18 Custom',
    'license': 'LGPL-3',
    'depends': ['simplify_access_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/sam_json_io_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
