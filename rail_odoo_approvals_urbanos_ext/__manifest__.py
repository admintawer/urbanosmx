# -*- coding: utf-8 -*-
{
    'name': 'Odoo Approval Urbanox MX',
    'version': '16.0.1.1',
    'category': 'Approvals',
    
    'description': '''
        Extention for urbanos MX
    ''',
    'author': 'Rail / Kevin Lopez',
    'price': 70,
    'currency': 'USD',
    'license': 'OPL-1',
    'depends': [
        'account','rail_odoo_approvals','purchase',
    ],
    'data': [
        
        # Add menu after actions.
        'views/account_move.xml',
        'views/account_payment.xml',
        
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'active': False,
    'application': True,
}
