# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64, xlrd, time
from collections import Counter
from datetime import datetime,date

class ImportBlanket(models.TransientModel):
    _name = 'import.blanket.wizard'
    _description = 'Import vendors agreement offers'

    requisition_id = fields.Many2one('purchase.requisition')
    vendor_domain = fields.Char()
    vendor_ids = fields.Many2many('res.partner', string="Proveedores", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    vendor_id = fields.Many2one('res.partner', string='Proveedor')
    xlsx_file = fields.Binary('File')

    def import_bl_xlsx(self):
        blanket_lines = self.env['pr.blanket.lines'].search([('requisition_id','=',self.requisition_id.id),('partner_id','=', self.vendor_id.id)])
        if blanket_lines:
            raise ValidationError('Ya existe una oferta importada para este proveedor, revisa por favor.')
        else:
            ncounter = 1
            skipped_line_no = []
            workbook = xlrd.open_workbook(file_contents=base64.decodebytes(self.xlsx_file))
            sheet = workbook.sheet_by_index(0)
            skip_header = True
            error = False
            for r in range(sheet.nrows):
                if skip_header:
                    skip_header = False
                    ncounter += 1
                    continue
                blanket_vals = {}
                if sheet.cell(r, 0).value not in (None, ""):
                    product = self.env['product.product'].search([('id','=', int(sheet.cell(r,0).value))])
                    if product:
                        blanket_vals.update({
                            'requisition_id': self.requisition_id.id,
                            'partner_id': self.vendor_id.id,
                            'product_id': product.id,
                        })
                        if sheet.cell(r, 4).value not in (None, ""):
                            price_unit = sheet.cell(r,4).value
                            blanket_vals.update({
                                'price_unit': price_unit
                            })
                        else:
                            error = True
                            skipped_line_no[str(ncounter)] = " - Hay un error en el precio unitario, por favor revisar"
                        if sheet.cell(r, 5).value not in (None, ""): 
                            d = sheet.cell(r,5).value
                            #schedule_date = str(datetime.strftime(schedule_date, '%Y-%m-%d').date())
                            year, month, day, hour, minutes, seconds = xlrd.xldate_as_tuple(d, workbook.datemode)
                            schedule_date = "{0}-{1}-{2}".format(year, month, day)
                            blanket_vals.update({
                                'schedule_date': schedule_date,
                            })
                        else:
                            error = True
                            skipped_line_no[str(ncounter)] = " - Hay un error en la fecha de entrega, por favor revisar"
                        blanket = self.env['pr.blanket.lines'].create(blanket_vals)
                    else:
                        skipped_line_no[str(ncounter)] = " - El codigo del producto no se encuentra, por favor revisar"
                        
                else:
                    skipped_line_no[str(ncounter)] = " - El codigo del producto esta vacio. "
                    ncounter += 1
                if error:
                    raise ValidationError(str(skipped_line_no))

                    