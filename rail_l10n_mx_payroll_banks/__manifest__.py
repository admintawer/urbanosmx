# -*- coding: utf-8 -*-
{
    'name': 'Rail Mexican Payroll Bank Dispersion',
    'version': '19.0.1.0.3',
    'category': 'Human Resources/Payroll',
    'summary': 'Layouts mexicanos de dispersión bancaria para nómina Odoo 19.',
    'description': """
Extiende el wizard nativo de reporte de pagos de nómina para generar layouts
mexicanos heredados de nomina_cfdi_bancos, sin depender de om_hr_payroll.
    """,
    'author': 'Rail / Tudu',
    'license': 'LGPL-3',
    'depends': [
        'rail_l10n_mx_payroll_base',
        'hr_payroll',
        'hr_payroll_account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_bank_views.xml',
        'views/res_partner_bank_views.xml',
        'wizard/hr_payroll_payment_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
