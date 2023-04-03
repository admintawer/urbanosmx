# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    asimilados = fields.Boolean("Asimilados")