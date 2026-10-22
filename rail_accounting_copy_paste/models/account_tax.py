# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountTax(models.Model):
    _inherit = 'account.tax'

    local_tax = fields.Boolean('Aplica Imp. Locales')
    local_tax_name = fields.Char('Nombre impuesto local')
    local_amount_type = fields.Selection(string="Tipo", selection=[('fixed','Monto'),('percent','Porcentaje')])

    @api.onchange('local_tax')
    def _onchange_local_tax(self):
        for tax in self:
            if tax.local_tax and 'l10n_mx_tax_type' in tax._fields:
                tax.l10n_mx_tax_type = 'local'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('local_tax'):
                vals['l10n_mx_tax_type'] = 'local'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('local_tax'):
            vals['l10n_mx_tax_type'] = 'local'
        return super().write(vals)
