# -*- coding: utf-8 -*-

from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    rail_sbc_variable = fields.Boolean(
        string='Integra variable IMSS/SBC',
        help='Marca reglas salariales que deben considerarse en el cálculo de variables para SBC bimestral.',
    )
    rail_sbc_variable_type = fields.Selection([
        ('all', 'Todo el monto'),
        ('excess_uma', 'Excedente de UMA'),
        ('excess_sbc', 'Excedente de SBC'),
    ], string='Tipo variable IMSS/SBC', default='all')
    rail_sbc_variable_amount = fields.Float(
        string='Parámetro exento IMSS/SBC',
        digits='Payroll',
        help='Porcentaje o importe usado por reglas marcadas como variable IMSS/SBC, según el tipo seleccionado.',
    )
