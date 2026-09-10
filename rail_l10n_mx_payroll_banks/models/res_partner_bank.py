# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    rail_mx_account_type = fields.Selection([
        ('checking', 'Cheques'),
        ('savings', 'Cuenta de ahorro / CLABE'),
        ('debit_card', 'Tarjeta de débito'),
        ('credit_card', 'Tarjeta de crédito'),
        ('clabe', 'CLABE interbancaria'),
    ], string='Tipo de cuenta MX',
       help='Tipo de cuenta requerido por layouts bancarios mexicanos. Mapea valores legacy: '
            'cheques, c_ahorro, t_debido/t_debito y t_credito.')
    rail_santander_bank_code = fields.Char(
        string='Clave Santander banco',
        size=5,
        help='Clave de banco requerida por el layout Santander mixto. En v18 estaba en hr.employee.',
    )
    rail_santander_place_code = fields.Char(
        string='Plaza Santander / Banxico',
        size=5,
        help='Plaza requerida por el layout Santander mixto. En v18 estaba en hr.employee.',
    )
