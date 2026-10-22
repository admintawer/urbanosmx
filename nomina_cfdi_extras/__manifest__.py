# -*- coding: utf-8 -*-
{
    'name': 'Nómina CFDI Extras v16 - Puente de migración a Odoo 19',
    'summary': 'Conserva préstamos, cuotas, viáticos e incidencias antes de depreciar el módulo legacy.',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'author': 'Rail',
    'license': 'AGPL-3',
    'depends': [
        'nomina_cfdi',
        'rail_l10n_mx_payroll_extras',
        'rail_l10n_mx_payroll_vacations',
        'rail_l10n_mx_payroll_reports',
    ],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
