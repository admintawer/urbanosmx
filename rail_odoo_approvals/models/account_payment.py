# -*- coding: utf-8 -*-

from odoo import fields, models

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    state = fields.Selection(selection_add=[('approved','Aprobado')], ondelete='default')