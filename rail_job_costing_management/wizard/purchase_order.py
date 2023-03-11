# -*- coding: utf-8 -*-

from datetime import date,time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class PurchaseOrderWizard(models.TransientModel):
    _name = 'purchase.order.wizard'

    supplier_ids = fields.Many2many(
        'res.partner',
        string='Suppliers',
        required=True,
    )
    product_line_ids = fields.One2many(
        'product.lines',
        'wizard_id',
        string='Product Lines',
    )

    @api.model
    def default_get(self, fields):
        rec = super(PurchaseOrderWizard, self).default_get(fields)
        active_id = self.env.context.get('active_id')
        job = self.env['job.costing'].browse(active_id)
        job_lines = self.env['job.cost.line'].search([('direct_id','=', active_id),('to_purchase','=',True)])
        vals = []
        for line in job_lines:
            vals.append((0,0,{
                            'product_id': line.product_id.id,
                            'description': line.description,
                            'quantity': line.remain_quantity,
                            'product_uom': line.uom_id.id,
                            'qty_available': line.product_id.qty_available,
                            'price_unit': line.cost_price,
                            'job_cost_line_id': line.id
                              }))
        rec.update({'product_line_ids': vals})
        return rec

    def create_purchase_requistion(self):
        active_id = self.env.context.get('active_id')
        job = self.env['job.costing'].browse(active_id)

        for vendor_id in self.supplier_ids:
            partner_id = vendor_id
            lines = self.product_line_ids

            order_line = []
            for line_id in lines:
                order_line.append((0, 0, {
                    'date_planned': datetime.now(),
                    'product_id': line_id.product_id.id,
                    'name': line_id.description,
                    'price_unit': line_id.price_unit,
                    'product_qty': line_id.quantity,
                    'product_uom': line_id.product_uom.id or False,
                    'job_cost_id': job.id,
                    'job_cost_line_id': line_id.job_cost_line_id.id,
                    'taxes_id': [(6,0, line_id.product_id.supplier_taxes_id.ids)],
                }))

            order = self.env['purchase.order'].create({'partner_id': partner_id.id,
                                               'date_order': datetime.now(),
                                               'origin': job.name,
                                               'order_line': order_line,
                                               'company_id': job.company_id.id
                                               })


        for l in job.job_cost_line_ids.filtered(lambda x: x.to_purchase == True):
            l.update({
                'to_purchase': False,
            })
        
        """ return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': order.id,
            'target': 'current',
        } """
        
    def cancel_close(self):
        picking = self.env['job.costing'].browse(self._context.get('active_ids', [])) 
        for l in picking.job_cost_line_ids.filtered(lambda x: x.to_purchase == True):
            l.update({
                'to_purchase': False,
            })       

class ProductLines(models.TransientModel):
    _name = 'product.lines'

    product_id = fields.Many2one(
        'product.product',
        string='Product'
    )
    description = fields.Text(
        'Descripcion'
    )
    quantity = fields.Float(
        'Quantity'
    )
    product_uom = fields.Many2one(
        'uom.uom',
        'Unit of Measure'
    )
    qty_available = fields.Float(
        'Quantity On Hand',
    )
    price_unit = fields.Float(
        'Precio'
    )
    wizard_id = fields.Many2one(
        'purchase.order.wizard',
    )
    job_cost_line_id = fields.Many2one(
        'job.cost.line'
    )
