# -*- coding: utf-8 -*-

from odoo import fields, models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _approval_allowed(self):
        """Returns whether the order qualifies to be approved by the current user"""

        """Overrided to force the approval for purchase administrators also"""
        self.ensure_one()
        return (
            self.company_id.po_double_validation == 'one_step'
            or (self.company_id.po_double_validation == 'two_step'
                and self.amount_total < self.env.company.currency_id._convert(
                    self.company_id.po_double_validation_amount, self.currency_id, self.company_id,
                    self.date_order or fields.Date.today()))
            or self.state == 'to approve')