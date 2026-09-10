# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Inverse Calculation',
    'version': '19.0.1.1.9',
    'category': 'Human Resources/Payroll',
    'summary': 'Cálculo inverso auditable para empleados y candidatos, con estructura salarial y detalle de reglas.',
    'description': """
Cálculo inverso de nómina mexicana migrado desde nomina_inverso v18.

No depende de om_hr_payroll ni de tablas.cfdi. Simula recibos con el motor nativo
hr_payroll/l10n_mx_hr_payroll y crea nuevas hr.version al confirmar.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'hr_payroll',
        'l10n_mx_hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_salary_rule_simulation_patch.xml',
        'views/rail_payroll_inverse_wizard_views.xml',
        'views/rail_payroll_inverse_batch_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
