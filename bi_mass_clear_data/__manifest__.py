# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name" : "Mass Clean and Delete Data Records",
    "version" : "16.0.0.1",
    "category" : "Extra Tools",
    'summary': 'Mass Clear Data Mass Delete data Mass clean data mass remove data Bulk Clear Data bulk Delete data bulk clean data bulk remove data remove data from database clean database clear database data clean from database',
    "description": """
    
        Clean Data Records in odoo,
        Mass Clean Data in odoo,
        Clean or Delete Unwanted Data in odoo,
        Clean All Data in odoo,
        Clean Sale Order Data in odoo,
        Clean Purchase Order Data in odoo,
        Clean Invoice Data in odoo,
        Clean Inventory Data in odoo,
        Clean Manufacturing Data in odoo,
        Clean Project Data in odoo,
    
    """,
    "author": "BrowseInfo",
    'price': 5,
    'currency': "EUR",
    'website': 'https://www.browseinfo.in',
    "depends" : ['base','account','stock','project','sale_management','purchase'],
    "data": [
        'security/ir.model.access.csv',
        'wizard/clear_data_view.xml',
    ],
    'license': 'OPL-1',
    "auto_install": False,
    "installable": True,
    "live_test_url":'https://youtu.be/bo-OSiC7cko',
    "images":["static/description/Banner.gif"],
}

