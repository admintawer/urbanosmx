# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll IMSS/SUA/IDSE',
    'version': '19.0.1.0.8',
    'category': 'Human Resources/Payroll',
    'summary': 'IMSS, SUA, IDSE y SBC para nómina mexicana Odoo 19 nativa.',
    'description': """
Migración funcional de los módulos nomina_cfdi_sua y nomina_cfdi_sbc hacia Odoo 19.

Este módulo no depende de om_hr_payroll ni de tablas.cfdi. Usa hr.version,
company_id.l10n_mx_imss_id, private_zip y parámetros/reglas nativas de v19.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'rail_l10n_mx_payroll_vacations',
        'hr_holidays',
        'hr_work_entry',
        'hr_work_entry_holidays',
        'l10n_mx_hr_payroll',
        'l10n_mx_hr_payroll_account_edi',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/hr_payroll_legacy_catalog_data.xml',
        'views/hr_employee_views.xml',
        'views/hr_version_views.xml',
        'views/hr_leave_views.xml',
        'views/rail_imss_incidence_views.xml',
        'wizards/exportar_cfdi_sua_views.xml',
        'wizards/retroactive_hire_wizard_views.xml',
        'wizards/wizard_sbc_bimestral_views.xml',
        'views/menus.xml',
        'data/imss_retroactive_hire_backfill_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
