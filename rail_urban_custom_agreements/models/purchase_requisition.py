# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    subtype = fields.Selection(string="Criterio", selection=[('time','Tiempo de entrega'),('price','Mejor precio')])
    vendor_qty = fields.Integer(string="Cnt. min. proveedores", related='type_id.vendor_qty')
    vendor_ids = fields.Many2many('res.partner', string="Vendor", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    @api.constrains('vendor_ids')
    def _check_vendor_qty(self):
        for r in self:
            if len(r.vendor_ids) < r.vendor_qty:
                raise ValidationError(_('Need comply with the vendor qty required for the agreement type'))

class PurchaseRequisitionType(models.Model):
    _inherit = 'purchase.requisition.type'

    vendor_qty = fields.Integer(string="Cnt. min. proveedores", default=1)