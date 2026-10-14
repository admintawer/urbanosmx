# -*- coding: utf-8 -*-

from odoo import fields, models

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_approve(self):
        ''' draft -> approved '''
        self.move_id.button_approve()