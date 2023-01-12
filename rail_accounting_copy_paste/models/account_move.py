# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    not_sync = fields.Boolean('Not sync to matrix')
    from_sync = fields.Boolean('Created from sync')
    source_company_id = fields.Many2one('res.company')
    synced = fields.Boolean('Matrix synced')
    matrix_ref = fields.Char('Matrix ref')