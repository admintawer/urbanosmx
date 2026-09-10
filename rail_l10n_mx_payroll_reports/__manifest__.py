# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Reports',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Reportes operativos de nómina mexicana para Odoo 19.',
    'description': 'Reportes operativos migrados desde nomina_cfdi_extras_ee hacia hr_payroll nativo Odoo 19. No depende de om_hr_payroll ni de tablas.cfdi.',
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'rail_l10n_mx_payroll_extras',
        'rail_l10n_mx_payroll_imss',
        'hr_payroll',
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rail_payroll_report_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
