# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountTax(models.Model):
    _inherit = 'account.tax'

    local_tax = fields.Boolean('Aplica Imp. Locales')
    local_tax_name = fields.Char('Nombre impuesto local')
    local_amount_type = fields.Selection(string="Tipo", selection=[('fixed','Monto'),('percent','Porcentaje')])