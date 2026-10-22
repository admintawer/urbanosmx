# -*- coding: utf-8 -*-

{
    'name': 'Data Clear Tools V19',
    'summary': """A powerful testing tool.Easily clear any odoo object data what you want. """,
    'author': 'Rail / Kevin Lopez ',
    'website': 'https://www.rail.com.mx',
    'version': '2.0',
    'category': 'Extra Tools',
    'license': 'OPL-1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'data/clear_data.xml',
        'security/ir.model.access.csv',
        'views/clear_data_views.xml',
    ],

}
