# -*- coding: utf-8 -*-
{
    'name': 'RAIL Mexican Payroll Accounting Extensions',
    'summary': 'Extensiones contables de nómina MX para Odoo 19',
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Payroll',
    'author': 'RAIL',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'rail_l10n_mx_payroll_imss',
        'hr_payroll_account',
        'accountant',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_salary_rule_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/wizard_poliza_imss_views.xml',
    ],
    'installable': True,
    'application': False,
}
