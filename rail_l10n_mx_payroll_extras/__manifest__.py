# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Extras',
    'version': '19.0.1.3.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Préstamos, descuentos periódicos y viáticos migrados a nómina v19 nativa.',
    'description': """
Extras de nómina mexicana migrados desde nomina_cfdi_extras_ee hacia Odoo 19.

Este módulo no depende de om_hr_payroll ni de nomina_cfdi_ee. Integra préstamos,
cuotas y viáticos usando hr.payslip.input e input_type_id nativos de Odoo 19.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'hr_payroll_account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_payslip_input_type_liquidation_ptu_data.xml',
        'data/l10n_mx_concept_liquidation_ptu_data.xml',
        'data/hr_payroll_structure_liquidation_ptu_data.xml',
        'data/hr_payroll_structure_viaticos_data.xml',
        'views/employee_loan_type_views.xml',
        'views/employee_loan_views.xml',
        'views/installment_line_views.xml',
        'views/viaticos_nomina_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payslip_views.xml',
        'wizard/payroll_liquidation_wizard_views.xml',
        'wizard/profit_sharing_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
