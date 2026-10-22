# -*- coding: utf-8 -*-

from odoo import fields, models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    rail_imss_disability_branch = fields.Selection([
        ('1', 'Riesgo de trabajo'),
        ('2', 'Enfermedad general'),
        ('3', 'Maternidad'),
    ], string='Ramo de seguro IMSS')
    rail_imss_risk_type = fields.Selection([
        ('0', 'No aplica'),
        ('1', 'Accidente de trabajo'),
        ('2', 'Accidente en trayecto'),
        ('3', 'Enfermedad profesional'),
    ], string='Tipo de riesgo IMSS')
    rail_imss_sequela = fields.Char(string='Secuela IMSS')
    rail_imss_control = fields.Char(string='Control IMSS')
    rail_imss_control2 = fields.Char(string='Control 2 IMSS')
    rail_imss_percentage = fields.Float(string='Porcentaje IMSS', digits='Payroll Rate')
    rail_imss_description = fields.Char(string='Descripción IMSS')
    rail_imss_disability_folio = fields.Char(string='Folio incapacidad IMSS')
    rail_imss_exported = fields.Boolean(string='Exportado SUA/IDSE', copy=False)
