# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    rail_payroll_compact_mode = fields.Selection([
        ('native', 'Usar agrupación nativa de Odoo'),
        ('account', 'Compactar por cuenta contable'),
        ('department', 'Compactar por departamento'),
    ], string='Compactación póliza nómina MX', default='native')

    rail_imss_fixed_fee_debit_account_id = fields.Many2one('account.account', string='IMSS cuota fija - Débito', check_company=True)
    rail_imss_fixed_fee_credit_account_id = fields.Many2one('account.account', string='IMSS cuota fija - Crédito', check_company=True)
    rail_imss_excess_debit_account_id = fields.Many2one('account.account', string='IMSS excedente - Débito', check_company=True)
    rail_imss_excess_credit_account_id = fields.Many2one('account.account', string='IMSS excedente - Crédito', check_company=True)
    rail_imss_cash_benefits_debit_account_id = fields.Many2one('account.account', string='IMSS prestaciones dinero - Débito', check_company=True)
    rail_imss_cash_benefits_credit_account_id = fields.Many2one('account.account', string='IMSS prestaciones dinero - Crédito', check_company=True)
    rail_imss_medical_expenses_debit_account_id = fields.Many2one('account.account', string='IMSS gastos médicos - Débito', check_company=True)
    rail_imss_medical_expenses_credit_account_id = fields.Many2one('account.account', string='IMSS gastos médicos - Crédito', check_company=True)
    rail_imss_work_risk_debit_account_id = fields.Many2one('account.account', string='IMSS riesgo trabajo - Débito', check_company=True)
    rail_imss_work_risk_credit_account_id = fields.Many2one('account.account', string='IMSS riesgo trabajo - Crédito', check_company=True)
    rail_imss_disability_life_debit_account_id = fields.Many2one('account.account', string='IMSS invalidez y vida - Débito', check_company=True)
    rail_imss_disability_life_credit_account_id = fields.Many2one('account.account', string='IMSS invalidez y vida - Crédito', check_company=True)
    rail_imss_childcare_debit_account_id = fields.Many2one('account.account', string='IMSS guarderías - Débito', check_company=True)
    rail_imss_childcare_credit_account_id = fields.Many2one('account.account', string='IMSS guarderías - Crédito', check_company=True)
    rail_imss_retirement_debit_account_id = fields.Many2one('account.account', string='IMSS retiro - Débito', check_company=True)
    rail_imss_retirement_credit_account_id = fields.Many2one('account.account', string='IMSS retiro - Crédito', check_company=True)
    rail_imss_severance_old_age_debit_account_id = fields.Many2one('account.account', string='IMSS cesantía y vejez - Débito', check_company=True)
    rail_imss_severance_old_age_credit_account_id = fields.Many2one('account.account', string='IMSS cesantía y vejez - Crédito', check_company=True)
    rail_imss_infonavit_debit_account_id = fields.Many2one('account.account', string='INFONAVIT patronal - Débito', check_company=True)
    rail_imss_infonavit_credit_account_id = fields.Many2one('account.account', string='INFONAVIT patronal - Crédito', check_company=True)
