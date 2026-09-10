# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Base',
    'version': '19.0.1.2.2',
    'category': 'Human Resources/Payroll',
    'summary': 'Base de migración de nómina mexicana v16/v18 hacia Odoo 19 nativo.',
    'description': """
Base común para migrar personalizaciones de nómina mexicana hacia Odoo 19.

Este módulo no depende de om_hr_payroll y usa hr.version como reemplazo técnico
de hr.contract para datos laborales versionables.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_payroll',
        'hr_payroll_account',
        'l10n_mx_hr_payroll',
        'l10n_mx_hr_payroll_account',
        'l10n_mx_hr_payroll_account_edi',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/other_entry_type_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_version_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/other_entry_type_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
