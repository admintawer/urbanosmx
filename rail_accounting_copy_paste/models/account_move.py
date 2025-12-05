# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class LocalTaxLines(models.Model):
     _name = 'account.move.local.tax.lines'
     _description = "Store the local tax deductions"

     move_id = fields.Many2one('account.move')
     tax_id = fields.Many2one('account.tax', string="Impuesto")
     amount = fields.Float('Monto')



class AccountMove(models.Model):
    _inherit = 'account.move'

    not_sync = fields.Boolean('Not sync to matrix', copy=False)
    from_sync = fields.Boolean('Created from sync', copy=False)
    source_company_id = fields.Many2one('res.company', copy=False)
    synced = fields.Boolean('Matrix synced', copy=False)
    matrix_ref = fields.Char('Matrix ref', copy=False)

    #-----------
    # LOCAL TAXES
    #-----------

    local_tax_ids = fields.One2many(string="Impuestos locales")

    def create_write_local_taxes(self):
        for r in self:

                        if local_tax:
                            for il in r.invoice_line_ids:
                                il.write({
                                    'tax_ids': [(4, local_tax.id, 0)]
                                })

    