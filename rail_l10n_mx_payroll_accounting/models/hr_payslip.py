# -*- coding: utf-8 -*-

from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _rail_get_account_side(self, line, account, debit, credit):
        """Return the accounting side currently prepared by hr_payroll_account.

        The native method calls _prepare_line_values twice, once with the debit
        account and once with the credit account. We infer the side from the
        configured accounts and generated debit/credit amounts.
        """
        debit_account = line.salary_rule_id.account_debit
        credit_account = line.salary_rule_id.account_credit
        if debit_account and account == debit_account:
            return 'debit'
        if credit_account and account == credit_account:
            return 'credit'
        if debit and not credit:
            return 'debit'
        if credit and not debit:
            return 'credit'
        return False

    def _prepare_line_values(self, line, account, date, debit, credit):
        side = self._rail_get_account_side(line, account, debit, credit)
        mapping = line.salary_rule_id.rail_get_special_account_mapping(side, self) if side else False
        target_account = mapping.account_id if mapping else account
        values = super()._prepare_line_values(line, target_account, date, debit, credit)
        if mapping and mapping.analytic_distribution:
            for vals in values:
                vals['analytic_distribution'] = mapping.analytic_distribution
        return values
