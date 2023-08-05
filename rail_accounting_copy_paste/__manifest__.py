# -*- coding: utf-8 -*-
{
    'name': "Multi company sync for Urban",

    'summary': """
        Take the account entries from multiple companies and consolidate into a single one""",

    'author': "Rail / Kevin Lopez",
    'website': "https://rail.com.mx",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customization',
    'version': '16.0.0.2',

    # any module necessary for this one to work correctly
    'depends': ['account','l10n_mx_edi'],

    # always loaded
    'data': [
        'data/cron.xml',
        'data/sync_error_email_template.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/account_tax.xml',
        'views/copy_paste_template.xml',
        'views/account_move.xml',
        'views/account_move_sync.xml',
        'views/cfdi_complement.xml',
    ],
    'license': 'LGPL-3',
}
