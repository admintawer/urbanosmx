# -*- coding: utf-8 -*-
{
    'name': 'Nómina CFDI v16 - Puente de migración a Odoo 19',
    'summary': 'Conserva y transfiere datos de nomina_cfdi hacia la nómina MX nativa y los módulos Rail.',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'author': 'Rail',
    'license': 'AGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'rail_l10n_mx_payroll_imss',
        'rail_l10n_mx_payroll_banks',
        'rail_l10n_mx_payroll_accounting',
    ],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
