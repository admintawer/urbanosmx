# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rail_payroll_compact_mode = fields.Selection(related='company_id.rail_payroll_compact_mode', readonly=False)

    rail_imss_fixed_fee_debit_account_id = fields.Many2one(related='company_id.rail_imss_fixed_fee_debit_account_id', readonly=False)
    rail_imss_fixed_fee_credit_account_id = fields.Many2one(related='company_id.rail_imss_fixed_fee_credit_account_id', readonly=False)
    rail_imss_excess_debit_account_id = fields.Many2one(related='company_id.rail_imss_excess_debit_account_id', readonly=False)
    rail_imss_excess_credit_account_id = fields.Many2one(related='company_id.rail_imss_excess_credit_account_id', readonly=False)
    rail_imss_cash_benefits_debit_account_id = fields.Many2one(related='company_id.rail_imss_cash_benefits_debit_account_id', readonly=False)
    rail_imss_cash_benefits_credit_account_id = fields.Many2one(related='company_id.rail_imss_cash_benefits_credit_account_id', readonly=False)
    rail_imss_medical_expenses_debit_account_id = fields.Many2one(related='company_id.rail_imss_medical_expenses_debit_account_id', readonly=False)
    rail_imss_medical_expenses_credit_account_id = fields.Many2one(related='company_id.rail_imss_medical_expenses_credit_account_id', readonly=False)
    rail_imss_work_risk_debit_account_id = fields.Many2one(related='company_id.rail_imss_work_risk_debit_account_id', readonly=False)
    rail_imss_work_risk_credit_account_id = fields.Many2one(related='company_id.rail_imss_work_risk_credit_account_id', readonly=False)
    rail_imss_disability_life_debit_account_id = fields.Many2one(related='company_id.rail_imss_disability_life_debit_account_id', readonly=False)
    rail_imss_disability_life_credit_account_id = fields.Many2one(related='company_id.rail_imss_disability_life_credit_account_id', readonly=False)
    rail_imss_childcare_debit_account_id = fields.Many2one(related='company_id.rail_imss_childcare_debit_account_id', readonly=False)
    rail_imss_childcare_credit_account_id = fields.Many2one(related='company_id.rail_imss_childcare_credit_account_id', readonly=False)
    rail_imss_retirement_debit_account_id = fields.Many2one(related='company_id.rail_imss_retirement_debit_account_id', readonly=False)
    rail_imss_retirement_credit_account_id = fields.Many2one(related='company_id.rail_imss_retirement_credit_account_id', readonly=False)
    rail_imss_severance_old_age_debit_account_id = fields.Many2one(related='company_id.rail_imss_severance_old_age_debit_account_id', readonly=False)
    rail_imss_severance_old_age_credit_account_id = fields.Many2one(related='company_id.rail_imss_severance_old_age_credit_account_id', readonly=False)
    rail_imss_infonavit_debit_account_id = fields.Many2one(related='company_id.rail_imss_infonavit_debit_account_id', readonly=False)
    rail_imss_infonavit_credit_account_id = fields.Many2one(related='company_id.rail_imss_infonavit_credit_account_id', readonly=False)
