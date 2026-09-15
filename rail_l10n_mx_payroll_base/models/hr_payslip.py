# -*- coding: utf-8 -*-

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('version_id.wage', 'version_id.wage_type')
    def _compute_daily_salary(self):
        """Keep the contractual MX fixed wage as a monthly amount.

        ``wage_type`` only distinguishes a fixed wage (``monthly`` in Odoo's
        technical selection) from an hourly wage.  It is not the payroll
        frequency.  For fixed-wage MX employees the business definition used by
        this migration is a contractual monthly salary, therefore the daily
        salary is ``wage / l10n_mx_days_per_month``.  ``schedule_pay`` remains
        the native source for the payment frequency (weekly, bi-weekly, monthly,
        etc.) and determines the payroll-period days.

        Hourly wages keep the native behavior and use ``hourly_wage``.
        """
        super()._compute_daily_salary()
        for payslip in self:
            if payslip.country_code != 'MX' or not payslip.version_id:
                continue
            if payslip.version_id.wage_type == 'hourly':
                continue
            days_per_month = float(payslip._rule_parameter('l10n_mx_days_per_month') or 0.0)
            if not days_per_month:
                continue
            monthly_wage = float(payslip.version_id._get_contract_wage() or 0.0)
            payslip.l10n_mx_daily_salary = monthly_wage / days_per_month
