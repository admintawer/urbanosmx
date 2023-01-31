# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_amount, format_date, formatLang, get_lang, groupby
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
        sheet.write(0, 0, 'Product code')
        sheet.write(0, 1, 'Product name')
        sheet.write(0, 2, 'Price')
        sheet.write(0, 3, 'Schedule date')
        row = 1
        _logger.critical('DATA'+str(data))
        _logger.critical('OBJECTS'+str(objects))
        for i in data:
            sheet.write(row, 0, i['product_code'])
            sheet.write(row, 1, i['product_name'])
            sheet.write(row, 2, 0.00)
            row += 1

class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition','abstract.mpld3.parser']

    subtype = fields.Selection(string="Criterio", selection=[('time','Tiempo de entrega'),('price','Mejor precio')])
    vendor_qty = fields.Integer(string="Cnt. min. proveedores", related='type_id.vendor_qty')
    vendor_ids = fields.Many2many('res.partner', string="Vendor", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    bl_count = fields.Integer(compute='_compute_blanket_number', string='Number of BLs')
    blanket_ids = fields.One2many('pr.blanket.lines', 'requisition_id')
    state = fields.Selection(selection_add=[('sent','Enviado'),('in_progress',)], ondelete={'sent': 'set default'})
    state_blanket_order = fields.Selection(selection_add=[('sent','Enviado'),('in_progress',)], ondelete={'sent': 'cascade'})
    vendor_emails = fields.Char(compute='_compute_vendor_emails')
    manual_aproval = fields.Boolean()

    @api.depends('vendor_ids')
    def _compute_vendor_emails(self):
        for r in self:
            emails = []
            ids = []
            if r.vendor_ids:
                for v in r.vendor_ids:
                    emails.append(v.email)
                    ids.append(str(v.id).replace('NewId_',''))
                r.vendor_emails = ','.join(emails)
            else:
                r.vendor_emails = ''
                    
    # ------------------------------------------------------------
    # MAIL.THREAD
    # ------------------------------------------------------------

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state == 'draft').write({'state': 'sent'})
        return super(PurchaseRequisition, self.with_context(mail_post_autofollow=self.env.context.get('mail_post_autofollow', True))).message_post(**kwargs)

    def _notify_by_email_prepare_rendering_context(self, message, msg_vals, model_description=False,
                                                   force_email_company=False, force_email_lang=False):
        render_context = super()._notify_by_email_prepare_rendering_context(
            message, msg_vals, model_description=model_description,
            force_email_company=force_email_company, force_email_lang=force_email_lang
        )
        subtitles = [render_context['record'].name]
        # don't show price on RFQ mail
        if self.state not in ['draft', 'sent']:
            if self.date_order:
                subtitles.append(_('%(amount)s due\N{NO-BREAK SPACE}%(date)s',
                                   amount=format_amount(self.env, self.amount_total, self.currency_id, lang_code=render_context.get('lang')),
                                   date=format_date(self.env, self.date_order, date_format='short', lang_code=render_context.get('lang'))
                                   ))
            else:
                subtitles.append(format_amount(self.env, self.amount_total, self.currency_id, lang_code=render_context.get('lang')))
        render_context['subtitles'] = subtitles
        return render_context

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


    def action_email_send(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data._xmlid_lookup('rail_urban_custom_agreements.email_template_rail_urban_bl')[2]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[2]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'purchase.requisition',
            'active_model': 'purchase.requisition',
            'active_id': self.ids[0],
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': "mail.mail_notification_layout_with_responsible_signature",
            'force_email': True,
            'mark_bl_as_sent': True,
        })

        lang = self.env.context.get('lang')
        if {'default_template_id', 'default_model', 'default_res_id'} <= ctx.keys():
            template = self.env['mail.template'].browse(ctx['default_template_id'])
            if template and template.lang:
                lang = template._render_lang([ctx['default_res_id']])[ctx['default_res_id']]

        self = self.with_context(lang=lang)
        if self.state in ['draft', 'sent']:
            ctx['model_description'] = _('Solicitud de licitacion')
        else:
            ctx['model_description'] = _('Licitacion aprobada')

        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }


    def send_email_with_xlsx(self):
        report = self.env.ref('rail_urban_custom_agreements.action_bl_xlsx')
        #raise UserError(report)
        product_list = []
        if not self.line_ids:
            raise ValidationError("Primero debes agregar productos a la licitacion")
        else:
            for r in self.line_ids:
                product = {
                    'product_code': r.product_id.id,
                    'product_name': r.product_id.display_name
                }
                product_list.append(product)
        generated_report = report._render_xlsx(report.id, self.id, product_list)

        data_record = base64.b64encode(generated_report[0])
        ir_values = {
            'name': 'Licitacion.xlsx',
            'type': 'binary',
            'datas': data_record,
            'store_fname': data_record,
            #'mimetype': 'application/vnd.ms-excel',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': 'purchase.requisition'
        }
        attachment = self.env['ir.attachment'].sudo().create(ir_values)
        #raise ValidationError(attachment)
        email_template = self.env.ref('rail_urban_custom_agreements.email_template_rail_urban_bl')
        if email_template:
            email_values = {
                'email_to': self.vendor_emails,
                'email_from': self.user_id.email,
            }
            email_template.attachment_ids = [4, attachment.id]
            email_template.send_mail(self.id, email_values=email_values)
            email_template.attachment_ids = [(5,0,0)]
            self.update({
                'state': 'sent',
            })
            
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

    def button_manual_aproval(self):
        for r in self:
            r.update({
                'manual_aproval': True
            })

    def action_in_progress(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("You cannot confirm agreement '%s' because there is no product line.", self.name))
        if self.type_id.quantity_copy == 'none' and self.vendor_id:
            for requisition_line in self.line_ids:
                if requisition_line.price_unit <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without price.'))
                if requisition_line.product_qty <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without quantity.'))
                requisition_line.create_supplier_info()
            self.write({'state': 'ongoing'})
        else:
            self.write({'state': 'in_progress'})
        # Set the sequence number regarding the requisition type
        if self.name == 'New':
            self.name = self.env['ir.sequence'].next_by_code('purchase.requisition.blanket.order')
        
        # Create PO
        vendors = self.line_ids.mapped('vendor_id.id')
        if not vendors:
            raise UserError(_('Por favor agregue al menos un proveedor para procesar las ordenes de compra!'))

        for vendor_id in vendors:
            partner_id = self.env['res.partner'].browse(vendor_id)
            lines = self.line_ids.filtered(lambda l: l.partner_id.id == vendor_id and l.purchase_id == False)

            order_line = []
            for line_id in lines:
                if line_id.purchase_id == False:
                    order_line.append((0, 0, {
                        'date_planned': line_id.schedule_date,
                        'product_id': line_id.product_id.id,
                        'name': line_id.product_id.name,
                        'price_unit': line_id.price_unit,
                        'product_qty': line_id.product_qty,
                        'product_uom': line_id.product_uom_id.id or False,
                    }))

            purchase = self.env['purchase.order'].create({
                'partner_id': partner_id.id,
                'date_order': line_id.schedule_date,
                'origin':self.name,
                'requisition_id': self.id,
                'order_line':order_line,
                })
            for line in lines:
                line.purchase_id = purchase


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    vendor_id = fields.Many2one('res.partner', string="Vendor", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    manual_aproval = fields.Boolean(related='requisition_id.manual_aproval') 
    purchase_id = fields.Many2one('purchase.order')   

class PurchaseRequisitionType(models.Model):
    _inherit = 'purchase.requisition.type'

    vendor_qty = fields.Integer(string="Cnt. min. proveedores", default=1)

class PurchaseRequisitionRfqs(models.Model):
    _name = 'pr.blanket.lines'

    partner_id = fields.Many2one('res.partner')
    requisition_line_id = fields.Many2one('purchase.requisition.line')
    requisition_id = fields.Many2one('purchase.requisition')
    product_id = fields.Many2one('product.product')
    price_unit = fields.Float()
    qty = fields.Float()
    schedule_date = fields.Date()