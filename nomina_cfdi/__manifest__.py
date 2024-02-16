# -*- coding: utf-8 -*-

{
    'name': 'Nomina Electrónica para México CFDI v4',
    'summary': 'Agrega funcionalidades para timbrar la nómina electrónica en México para cfdi v4.',
    'author': 'Rail / Kevin Lopez',
    'version': '16.0.1',
    'category': 'Employees',
    'depends': [
        'hr_payroll', 'l10n_mx_edi','hr_payroll_account'
    ],
    'data': [
        'data/inputs.xml',
        'data/sequence_data.xml',
        'data/cron.xml',
        'data/nomina.otropago.csv',
        'data/nomina.percepcion.csv',
        'data/nomina.deduccion.csv',
        'report/report_payslip.xml',
        'views/hr_employee_view.xml',
        'views/hr_contract_view.xml',
        'views/hr_salary_view.xml',
        'views/hr_payroll_payslip_view.xml',
        'views/tablas_cfdi_view.xml',
        'views/res_company_view.xml',
        'views/res_bank_view.xml',
        'views/hr_payroll_structure.xml',
        'data/mail_template_data.xml',
        'security/ir.model.access.csv',
        'data/res.bank.csv',
        'views/menu.xml',
        'views/horas_extras_view.xml',
        'wizard/wizard_liquidacion_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
