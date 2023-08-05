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

    #-----------
    # ISERTP WITHOLDING
    #-----------

    use_isertp = fields.Boolean(string="Impuestos locales")

    isertp_amount = fields.Float(string="ISERTP")
    servicio_control = fields.Float(string="Servicios de control")
    icic = fields.Float(string="I.C.I.C.")
    cmicem = fields.Float(string="C.M.I.C.E.M")
    impuestos_locales = fields.Float("Impuestos Locales")

    def update_isertp(self):
        for r in self:
            if r.use_isertp:
                isertp_val = False
                for l in r.line_ids:
                    for t in l.tax_ids:
                        if t.name == 'Impuestos Locales':
                            isertp_val = True
                if isertp_val:
                    raise ValidationError("Ya estan establecidos los impuestos locales.\n"\
                                        +"Antes de calcular el ISERTP debes remover dichos impuestos de todas las lineas implicadas")
                else:
                    isertp = self.env['account.tax'].search([('name','=','3.0% ISERTP'),('company_id','=',self.company_id.id)])
                    if isertp:
                        isertp.update({
                            'amount': self.isertp_amount * -1,
                        })
                        local_tax = self.env['account.tax'].search([('name','=','Impuestos Locales'),('company_id','=',self.company_id.id)])
                        if local_tax:
                            for il in r.invoice_line_ids:
                                il.write({
                                    'tax_ids': [(4, local_tax.id, 0)]
                                })
                    else:
                        raise ValidationError("No se ha encontraro el impuesto relacionado a ISERTP \n"\
                                            +"Verifica que haya un impuesto creado con el nombre '3.0% ISERTP'\n"\
                                                + "Si no sabes donde buscarlo contacta a soporte.")
    