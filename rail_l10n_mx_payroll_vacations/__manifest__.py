# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Vacations',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Control legacy de saldos vacacionales sobre hr.version para nómina mexicana.',
    'description': """
Control de vacaciones migrado desde nómina v18 hacia Odoo 19.

Este módulo no usa om_hr_payroll ni hr.contract. Mantiene saldos vacacionales
por hr.version, consume días al validar ausencias de vacaciones y los devuelve
al cancelar/rechazar, respetando el motor nativo de ausencias y work entries de Odoo 19.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'hr_holidays',
        'hr_work_entry_holidays',
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/hr_leave_type_views.xml',
        'views/rail_vacation_line_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
