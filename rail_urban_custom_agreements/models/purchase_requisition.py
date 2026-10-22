# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError
from datetime import datetime
import base64, logging
_logger = logging.getLogger(__name__)


class ExcelReport(models.AbstractModel):
    _name = 'report.rail_urban_custom_agreements.report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'BL xlsx'

    def generate_xlsx_report(self, workbook, data, objects):
        sheet = workbook.add_worksheet('LICITACION')
        """ head_format = workbook.add_format({
            'align': 'center',
            'bold': True,
            'font_size': '12px',
        })
        data_format = workbook.add_format({
            'font_size': '10px',
        }) """

        #Write XLSX
        sheet.write(0, 0, 'Codigo')
        sheet.write(0, 1, 'Producto')
        sheet.write(0, 2, 'Cantidad')
        sheet.write(0, 3, 'UdM')
        sheet.write(0, 4, 'Precio')
        sheet.write(0, 5, 'Fecha entrega')
        sheet.write(0, 6, 'Notas')
        row = 1
        _logger.critical('DATA'+str(data))
        _logger.critical('OBJECTS'+str(objects))
        for i in data:
            sheet.write(row, 0, i['product_code'])
            sheet.write(row, 1, i['product_name'])
            sheet.write(row, 2, i['qty'])
            sheet.write(row, 3, i['product_uom'])
            sheet.write(row, 4, 0.00)
            sheet.write(row, 6, i['description'])
            row += 1

class PurchaseRequisitionType(models.Model):
    """Legacy agreement type retained so v16 foreign keys remain readable."""

    _name = 'purchase.requisition.type'
    _description = 'Legacy Purchase Agreement Type'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    exclusive = fields.Selection([('exclusive', 'Exclusive'), ('multiple', 'Multiple')], default='multiple')
    quantity_copy = fields.Selection([('none', 'Do not copy'), ('copy', 'Copy')], default='none')
    vendor_qty = fields.Integer(string="Cnt. min. proveedores", default=1)


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    subtype = fields.Selection(string="Criterio", selection=[('time','Tiempo de entrega'),('price','Mejor precio'),('time_price', 'Tiempo + Precio')])
    type_id = fields.Many2one('purchase.requisition.type', string='Legacy Agreement Type', ondelete='set null')
    vendor_qty = fields.Integer(string="Cnt. min. proveedores", related='type_id.vendor_qty', readonly=True)
    vendor_ids = fields.Many2many('res.partner', string="Proveedores", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    bl_count = fields.Integer(compute='_compute_blanket_number', string='Number of BLs')
    blanket_ids = fields.One2many('pr.blanket.lines', 'requisition_id')
    state = fields.Selection(
        selection_add=[
            ('sent', 'Enviado'),
            ('in_progress', 'En progreso'),
            ('ongoing', 'Vigente'),
            ('open', 'Abierto'),
        ],
        ondelete={
            'sent': 'set default',
            'in_progress': 'set default',
            'ongoing': 'set default',
            'open': 'set default',
        },
    )
    state_blanket_order = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('in_progress', 'En progreso'),
        ('open', 'Abierto'),
        ('done', 'Cerrado'),
    ], default='draft')
    origin = fields.Char(string='Origen')
    ordering_date = fields.Date(string='Fecha de pedido', default=fields.Date.context_today)
    vendor_emails = fields.Char(compute='_compute_vendor_emails')
    manual_aproval = fields.Boolean()

    @api.depends('vendor_ids')
    def _compute_vendor_emails(self):
        for r in self:
            emails = []
            if r.vendor_ids:
                for v in r.vendor_ids:
                    if v.email:
                        emails.append(v.email)
                    else:
                        raise ValidationError("No puedes agregar un proveedor sin email, por favor primero registra un correo electronico valido")
                r.vendor_emails = ','.join(emails)
            else:
                r.vendor_emails = ''
                    
    # ------------------------------------------------------------
    # MAIL.THREAD
    # ------------------------------------------------------------

    def message_post(self, **kwargs):
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state == 'draft').write({'state': 'sent'})
        return super(PurchaseRequisition, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'in_progress':
            if init_values['state'] == 'to approve':
                return self.env.ref('rail_urban_custom_agreements.mt_rfq_approved')
            return self.env.ref('rail_urban_custom_agreements.mt_bl_confirmed')
        elif 'state' in init_values and self.state == 'open':
            return self.env.ref('rail_urban_custom_agreements.mt_bl_confirmed')
        elif 'state' in init_values and self.state == 'done':
            return self.env.ref('rail_urban_custom_agreements.mt_bl_done')
        elif 'state' in init_values and self.state == 'sent':
            return self.env.ref('rail_urban_custom_agreements.mt_rfq_sent')
        return super(PurchaseRequisition, self)._track_subtype(init_values)


    def send_email_with_xlsx(self):
        self.ensure_one()
        lang = self.env.context.get('lang')
        report = self.env.ref('rail_urban_custom_agreements.action_bl_xlsx')
        product_list = []
        if not self.line_ids:
            raise ValidationError("Primero debes agregar productos a la licitacion")
        else:
            for r in self.line_ids:
                product = {
                    'product_code': r.product_id.id,
                    'product_name': r.product_id.display_name,
                    'description': r.product_description_variants if r.product_description_variants else '',
                    'qty': r.product_qty,
                    'product_uom': r.product_uom_id.display_name
                }
                product_list.append(product)
        generated_report = report._render_xlsx(report.id, self.id, product_list)

        data_record = base64.b64encode(generated_report[0])
        ir_values = {
            'name': 'Licitacion'+self.name+'.xlsx',
            'type': 'binary',
            'datas': data_record,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'purchase.requisition',
            'res_id': self.id,
        }
        attachment = self.env['ir.attachment'].sudo().create(ir_values)
        email_template = self.env.ref('rail_urban_custom_agreements.email_template_rail_urban_bl').sudo()
        if email_template and email_template.lang:
            lang = email_template._render_lang(self.ids)[self.id]
            email_values = {
                'email_to': self.user_id.email,
                'email_bcc': self.vendor_emails,
                'email_from': self.user_id.email,
                'attachment_ids': [(4, attachment.id)],
            }
            email_template.send_mail(self.id, force_send=True, email_values=email_values)

        self.state = 'sent'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Correo enviado'), 'type': 'success', 'sticky': False},
        }

            
    @api.depends('blanket_ids')
    def _compute_blanket_number(self):
        for r in self:
            if r.line_ids:
                r.bl_count = len(r.blanket_ids) / len(r.line_ids)
            else:
                r.bl_count = 0

    @api.constrains('vendor_ids')
    def _check_vendor_qty(self):
        for r in self:
            if len(r.vendor_ids) < r.vendor_qty:
                raise ValidationError(_('Need comply with the vendor qty required for the agreement type'))

    def button_automatic_aproval(self):
        for r in self:
            bl_object = self.env['pr.blanket.lines']
            r.update({
                'manual_aproval': False,
            })
            if r.subtype == 'time':
                for l in r.line_ids:
                    bl_time = bl_object.search([('requisition_id','=',r.id),
                                                ('product_id','=',l.product_id.id)],order='schedule_date asc', limit=1)
                    bl_time.update({
                        'requisition_line_id': l.id,
                    })
                    l.update({
                        'vendor_id': bl_time.partner_id,
                        'schedule_date': bl_time.schedule_date,
                        'price_unit': bl_time.price_unit,
                    })
            elif r.subtype == 'price':
                for l in r.line_ids:
                    bl_price = bl_object.search([('requisition_id','=',r.id),
                                                ('product_id','=',l.product_id.id)],order='price_unit asc', limit=1)
                    bl_price.update({
                        'requisition_line_id': l.id,
                    })
                    l.update({
                        'vendor_id': bl_price.partner_id,
                        'schedule_date': bl_price.schedule_date,
                        'price_unit': bl_price.price_unit
                    })
            elif r.subtype == 'time_price':
                for l in r.line_ids:
                    bl_timeprice = bl_object.search([('requisition_id','=',r.id),
                                                ('product_id','=',l.product_id.id)],order='score asc', limit=1)
                    bl_timeprice.update({
                        'requisition_line_id': l.id,
                    })
                    l.update({
                        'vendor_id': bl_timeprice.partner_id,
                        'schedule_date': bl_timeprice.schedule_date,
                        'price_unit': bl_timeprice.price_unit
                    })

    def button_manual_aproval(self):
        for r in self:
            r.update({
                'manual_aproval': True
            })

    def action_in_progress(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("You cannot confirm agreement '%s' because there is no product line.", self.name))
        if self.requisition_type == 'blanket_order' and self.vendor_id:
            for requisition_line in self.line_ids:
                if requisition_line.price_unit <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without price.'))
                if requisition_line.product_qty <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without quantity.'))
                requisition_line._create_supplier_info()
            self.write({'state': 'ongoing'})
        else:
            self.write({'state': 'in_progress'})
        
        # Create PO
        vendors = self.line_ids.mapped('vendor_id.id')
        if not vendors:
            raise UserError(_('Por favor agregue al menos un proveedor para procesar las ordenes de compra!'))

        for vendor_id in vendors:
            partner_id = self.env['res.partner'].browse(vendor_id)
            lines = self.line_ids.filtered(lambda l: l.vendor_id.id == vendor_id and not l.purchase_id)
            order_line = []
            for line_id in lines:
                if  not line_id.purchase_id:
                    order_line.append((0, 0, {
                        'date_planned': line_id.schedule_date,
                        'product_id': line_id.product_id.id,
                        'name': line_id.product_id.name,
                        'price_unit': line_id.price_unit,
                        'product_qty': line_id.product_qty,
                        'product_uom_id': line_id.product_uom_id.id or False,
                        'taxes_id': [(6, 0, line_id.product_id.supplier_taxes_id.ids)],
                    }))

            purchase = self.env['purchase.order'].create({
                'partner_id': partner_id.id,
                'date_order': datetime.now(),
                'origin':self.name,
                'requisition_id': self.id,
                'order_line':order_line,
                })
            for line in lines:
                line.purchase_id = purchase.id

class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    vendor_id = fields.Many2one('res.partner', string="Vendor", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    schedule_date = fields.Date(string='Fecha de entrega')
    manual_aproval = fields.Boolean(related='requisition_id.manual_aproval') 
    purchase_id = fields.Many2one('purchase.order')   

class PurchaseRequisitionRfqs(models.Model):
    _name = 'pr.blanket.lines'
    _description = 'Blanket agreements analysis'

    partner_id = fields.Many2one('res.partner')
    requisition_line_id = fields.Many2one('purchase.requisition.line')
    requisition_id = fields.Many2one('purchase.requisition')
    product_id = fields.Many2one('product.product')
    price_unit = fields.Float()
    qty = fields.Float()
    schedule_date = fields.Date()
    ordering_date = fields.Date(related='requisition_id.ordering_date')
    score = fields.Float(compute = '_compute_score')

    @api.depends('schedule_date')
    def _compute_score(self):
        for r in self:
            if r.schedule_date and r.ordering_date:
                if r.schedule_date < r.ordering_date:
                    raise ValidationError('La fecha de entrega no puede ser menor a la fecha de pedido, revisa los datos por favor')
                else:
                    r.score = (r.schedule_date - r.ordering_date).days + r.price_unit
            else:
                r.score = 0
