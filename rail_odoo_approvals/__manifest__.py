# -*- coding: utf-8 -*-
{
    'name': 'Odoo Approval',
    'version': '16.0.1.0',
    'category': 'Approvals',
    
    'description': '''
    Create and validate approval requests. Each request can be approved by many levels of different managers
    ''',
    'author': 'Rail / Kevin Lopez',
    'price': 70,
    'currency': 'USD',
    'license': 'OPL-1',
    'depends': [
        'mail',
        'product'
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',

        # wizard
        'wizard/refused_reason_views.xml',
        'wizard/cancel_approval_views.xml',
        'wizard/change_approver_views.xml',
        'wizard/request_approval_views.xml',
        'wizard/rework_approval_views.xml',
        'wizard/test_approval_views.xml',

        'views/multi_approval_type_views.xml',
        'views/multi_approval_views.xml',

        'views/multi_approval_type_views_config.xml',
        'views/multi_approval_views_config.xml',

        # Add actions after all views.
        'views/actions.xml',

        # Add menu after actions.
        'views/menu.xml',
        
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'active': False,
    'application': True,
}
