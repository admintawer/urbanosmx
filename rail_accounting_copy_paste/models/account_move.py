# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    not_sync = fields.Boolean('Not sync to matrix', copy=False)
    from_sync = fields.Boolean('Created from sync', copy=False)
    source_company_id = fields.Many2one('res.company', copy=False)
    synced = fields.Boolean('Matrix synced', copy=False)
    matrix_ref = fields.Char('Matrix ref', copy=False)