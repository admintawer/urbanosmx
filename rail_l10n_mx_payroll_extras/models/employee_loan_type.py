# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DEDUCTION_TYPE_SELECTION = [
    ('1', 'Préstamo'),
    ('2', 'Descuento periódico 1'),
    ('3', 'Descuento periódico 2'),
    ('4', 'Descuento periódico 3'),
    ('5', 'Descuento periódico 4'),
    ('6', 'Descuento periódico 5'),
    ('7', 'Descuento periódico 6'),
    ('8', 'Descuento periódico 7'),
    ('9', 'Descuento periódico 8'),
    ('10', 'Descuento periódico 9'),
    ('11', 'Descuento periódico 10'),
    ('12', 'Descuento periódico 11'),
    ('13', 'Descuento periódico 12'),
    ('14', 'Descuento periódico 13'),
    ('15', 'Descuento periódico 14'),
    ('16', 'Descuento periódico 15'),
]


class EmployeeLoanType(models.Model):
    _name = 'employee.loan.type'
    _description = 'Tipo de préstamo/descuento de nómina'
    _order = 'name'

    name = fields.Char('Nombre', required=True)
    loan_limit = fields.Float('Límite del monto', default=5000.0, required=True)
    loan_term = fields.Integer('Plazo máximo', default=12, required=True)
    is_apply_interest = fields.Boolean('Aplicar interés')
    interest_rate = fields.Float('Tasa de interés', default=0.0)
    interest_type = fields.Selection([
        ('liner', 'Sobre monto total'),
        ('reduce', 'Sobre saldo pendiente'),
    ], string='Tipo de interés', default='liner')
    payment_period = fields.Selection([
        ('weekly', 'Semanal'),
        ('biweekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], string='Periodo de pago', default='biweekly', required=True)
    # Campo legacy para facilitar migración desde v18.
    periodo_de_pago = fields.Selection([
        ('Semanal', 'Semanal'),
        ('Quincenal', 'Quincenal'),
        ('Mensual', 'Mensual'),
    ], string='Periodo legacy v18')
    tipo_deduccion = fields.Selection(
        DEDUCTION_TYPE_SELECTION,
        string='Tipo de deducción legacy',
        default='1',
        required=True,
        help='Clasificación usada en v18. En v19 se mapea a tipos de input de nómina.',
    )
    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Input de nómina principal',
        help='Input nativo de Odoo 19 que recibirá el monto de la cuota.',
    )
    interest_input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Input de interés',
        help='Input nativo de Odoo 19 para registrar el interés de la cuota, si aplica.',
    )
    loan_account = fields.Many2one('account.account', string='Cuenta de préstamo')
    interest_account = fields.Many2one('account.account', string='Cuenta de intereses')
    journal_id = fields.Many2one('account.journal', string='Diario')
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    @api.onchange('periodo_de_pago')
    def _onchange_periodo_de_pago(self):
        mapping = {
            'Semanal': 'weekly',
            'Quincenal': 'biweekly',
            'Mensual': 'monthly',
        }
        for record in self:
            if record.periodo_de_pago:
                record.payment_period = mapping.get(record.periodo_de_pago, record.payment_period)

    @api.constrains('loan_limit', 'loan_term', 'interest_rate', 'interest_type')
    def _check_amounts(self):
        for loan_type in self:
            if loan_type.loan_limit <= 0:
                raise ValidationError(_('El límite del monto debe ser mayor a cero.'))
            if loan_type.loan_term <= 0:
                raise ValidationError(_('El plazo máximo debe ser mayor a cero.'))
            if loan_type.is_apply_interest and loan_type.interest_rate <= 0:
                raise ValidationError(_('La tasa de interés debe ser mayor a cero cuando se aplica interés.'))
            if loan_type.is_apply_interest and not loan_type.interest_type:
                raise ValidationError(_('Seleccione el tipo de interés.'))

    def rail_get_default_input_type(self):
        self.ensure_one()
        if self.input_type_id:
            return self.input_type_id
        if self.tipo_deduccion == '1':
            return self.env.ref('rail_l10n_mx_payroll_extras.input_type_loan', raise_if_not_found=False)
        xmlid = 'rail_l10n_mx_payroll_extras.input_type_discount_%02d' % (int(self.tipo_deduccion) - 1)
        return self.env.ref(xmlid, raise_if_not_found=False)

    def rail_get_interest_input_type(self):
        self.ensure_one()
        return self.interest_input_type_id or self.env.ref(
            'rail_l10n_mx_payroll_extras.input_type_loan_interest',
            raise_if_not_found=False,
        )
