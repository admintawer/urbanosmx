# -*- coding: utf-8 -*-

from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'

    rail_mx_bank_code = fields.Char(
        string='Clave banco MX / Banxico',
        size=5,
        help='Clave de banco usada por layouts mexicanos heredados de dispersión. '
             'En v18 algunos layouts la tomaban de banco.c_banco.',
    )
