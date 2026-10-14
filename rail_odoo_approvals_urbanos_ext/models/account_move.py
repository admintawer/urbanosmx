# -*- coding: utf-8 -*-

from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    state = fields.Selection(selection_add=[('approved','Aprobado')], ondelete={'approved': 'set default'})

    def button_approve(self):
        for r in self:
            r.write({
                'state': 'approved',
            })