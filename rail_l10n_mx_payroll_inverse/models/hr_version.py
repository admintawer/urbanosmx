# -*- coding: utf-8 -*-

from odoo import models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _get_contract_wage(self):
        """Allow inverse-payroll simulations without writing the real version wage.

        Odoo 19 Mexican salary rules read the wage from ``version._get_contract_wage()``.
        During inverse calculation we pass the candidate wage in context, so the
        simulated payslip uses that amount while the real hr.version remains unchanged.
        """
        candidate = self.env.context.get('rail_inverse_candidate_wage')
        version_id = self.env.context.get('rail_inverse_version_id')
        if candidate is not None and self and (not version_id or self.id == version_id):
            return float(candidate or 0.0)
        return super()._get_contract_wage()
