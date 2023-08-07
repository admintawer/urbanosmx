# -*- coding: utf-8 -*-

from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    job_sheet_id = fields.Many2one('job.costing')