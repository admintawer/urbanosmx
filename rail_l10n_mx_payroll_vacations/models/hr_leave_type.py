# -*- coding: utf-8 -*-

from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    code = fields.Char(
        string='Código legacy',
        help='Código migrado desde v18. Use VAC para identificar vacaciones en el control legacy MX.',
    )
    rail_is_vacation = fields.Boolean(
        string='Controlar saldo vacacional MX',
        help='Si está activo, las ausencias de este tipo consumen/devolven saldo de rail.vacation.line.',
    )
