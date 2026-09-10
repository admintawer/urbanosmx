# -*- coding: utf-8 -*-

from calendar import monthrange
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError, UserError


class EmployeeLoan(models.Model):
    _name = 'employee.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Préstamo / descuento de empleado'
    _order = 'name desc'

    name = fields.Char('Referencia', default='/', copy=False, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('hr_approval', 'Aprobado'),
        ('paid', 'Pagado/entregado'),
        ('done', 'Activo en nómina'),
        ('close', 'Cerrado'),
        ('reject', 'Rechazado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, tracking=True)
    version_id = fields.Many2one(
        'hr.version',
        string='Versión laboral',
        compute='_compute_version_id',
        store=True,
        readonly=False,
        help='Versión vigente a la fecha de inicio. Reemplaza el uso de hr.contract en v18.',
    )
    department_id = fields.Many2one('hr.department', string='Departamento', related='employee_id.department_id', store=True, readonly=False)
    job_id = fields.Many2one('hr.job', string='Puesto de trabajo', related='employee_id.job_id', store=True, readonly=False)
    date = fields.Date('Fecha', default=fields.Date.context_today, required=True)
    start_date = fields.Date('Fecha de inicio', default=fields.Date.context_today, required=True)
    end_date = fields.Date('Fecha de término', compute='_compute_end_date', store=True)
    term = fields.Integer('Plazos', required=True, default=1)
    loan_type_id = fields.Many2one('employee.loan.type', string='Tipo', required=True)
    payment_method = fields.Selection([('by_payslip', 'Nómina')], string='Método de pago', default='by_payslip', required=True)
    loan_amount = fields.Float('Monto', required=True)
    paid_amount = fields.Float('Monto pagado', compute='_compute_paid_amount', store=True)
    remaing_amount = fields.Float('Cantidad restante', compute='_compute_remaining_amount', store=True)
    installment_amount = fields.Float('Cantidad por plazo', compute='_compute_installment_amount', store=True)
    is_apply_interest = fields.Boolean('Aplicar interés')
    interest_type = fields.Selection([('liner', 'Sobre monto total'), ('reduce', 'Sobre saldo pendiente')], string='Tipo de interés')
    interest_rate = fields.Float('Tasa de interés')
    interest_amount = fields.Float('Monto de interés', compute='_compute_interest_amount', store=True)
    installment_lines = fields.One2many('installment.line', 'loan_id', string='Cuotas')
    notes = fields.Text('Razón / notas')
    is_close = fields.Boolean('Listo para cerrar', compute='_compute_is_close')
    move_id = fields.Many2one('account.move', string='Asiento de entrega', copy=False)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.depends('employee_id', 'start_date')
    def _compute_version_id(self):
        for loan in self:
            if loan.employee_id and loan.start_date:
                loan.version_id = loan.employee_id._get_version(loan.start_date)
            elif loan.employee_id:
                loan.version_id = loan.employee_id.version_id
            else:
                loan.version_id = False

    @api.depends(
        'start_date', 'term', 'loan_type_id.payment_period', 'loan_type_id.periodo_de_pago',
        'installment_lines.date', 'installment_lines.is_skip',
    )
    def _compute_end_date(self):
        for loan in self:
            active_dates = loan.installment_lines.filtered(lambda line: not line.is_skip).mapped('date')
            if active_dates:
                loan.end_date = max(active_dates)
            elif loan.start_date and loan.term and loan.loan_type_id:
                loan.end_date = loan._get_installment_date(loan.term - 1)
            else:
                loan.end_date = False

    @api.depends('loan_amount', 'term')
    def _compute_installment_amount(self):
        for loan in self:
            loan.installment_amount = loan.loan_amount / loan.term if loan.loan_amount and loan.term else 0.0

    @api.depends('installment_lines.is_paid', 'installment_lines.is_skip', 'installment_lines.total_installment')
    def _compute_paid_amount(self):
        for loan in self:
            loan.paid_amount = sum(
                loan.installment_lines.filtered(lambda line: line.is_paid and not line.is_skip).mapped('total_installment')
            )

    @api.depends('loan_amount', 'interest_amount', 'paid_amount')
    def _compute_remaining_amount(self):
        for loan in self:
            loan.remaing_amount = (loan.loan_amount + loan.interest_amount) - loan.paid_amount

    @api.depends(
        'loan_amount', 'term', 'is_apply_interest', 'interest_rate', 'interest_type',
        'installment_lines.ins_interest', 'installment_lines.is_skip',
    )
    def _compute_interest_amount(self):
        for loan in self:
            if not loan.is_apply_interest:
                loan.interest_amount = 0.0
            elif loan.interest_type == 'reduce' and loan.installment_lines:
                loan.interest_amount = sum(
                    loan.installment_lines.filtered(lambda line: not line.is_skip).mapped('ins_interest')
                )
            else:
                loan.interest_amount = (loan.loan_amount * loan.interest_rate) / 100.0

    def _compute_is_close(self):
        for loan in self:
            loan.is_close = loan.state == 'done' and loan.remaing_amount <= 0.01

    @api.onchange('loan_type_id')
    def _onchange_loan_type_id(self):
        for loan in self:
            if not loan.loan_type_id:
                continue
            loan.term = loan.loan_type_id.loan_term
            loan.is_apply_interest = loan.loan_type_id.is_apply_interest
            loan.interest_rate = loan.loan_type_id.interest_rate
            loan.interest_type = loan.loan_type_id.interest_type

    @api.constrains('loan_amount', 'term', 'loan_type_id')
    def _check_amount_term(self):
        for loan in self:
            if loan.loan_amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero.'))
            if loan.loan_type_id and loan.loan_amount > loan.loan_type_id.loan_limit:
                raise ValidationError(_('El monto máximo permitido para este tipo es %s.') % loan.loan_type_id.loan_limit)
            if loan.term <= 0:
                raise ValidationError(_('El plazo debe ser mayor a cero.'))
            if loan.loan_type_id and loan.term > loan.loan_type_id.loan_term:
                raise ValidationError(_('El plazo máximo permitido para este tipo es %s.') % loan.loan_type_id.loan_term)

    @api.constrains('employee_id', 'date')
    def _check_loan_year_limit(self):
        for loan in self:
            if not loan.employee_id or not loan.date or not loan.employee_id.loan_request:
                continue
            start = date(loan.date.year, 1, 1)
            stop = date(loan.date.year, 12, 31)
            count = self.search_count([
                ('employee_id', '=', loan.employee_id.id),
                ('date', '>=', start),
                ('date', '<=', stop),
                ('state', 'not in', ('cancel', 'reject')),
                ('id', '!=', loan.id),
            ])
            if count >= loan.employee_id.loan_request:
                raise ValidationError(_('Puedes crear un máximo de %s préstamo(s) por año para este empleado.') % loan.employee_id.loan_request)

    def _get_installment_date(self, index):
        self.ensure_one()
        base_date = self.start_date
        period = self.loan_type_id.payment_period
        if self.loan_type_id.periodo_de_pago:
            period = {'Semanal': 'weekly', 'Quincenal': 'biweekly', 'Mensual': 'monthly'}.get(self.loan_type_id.periodo_de_pago, period)
        if period == 'weekly':
            return base_date + relativedelta(weeks=index)
        if period == 'monthly':
            return base_date + relativedelta(months=index)
        # Quincenal: conserva la lógica v18 de acercarse a 15/fin de mes.
        raw_date = base_date + relativedelta(days=index * 15)
        month_last_day = monthrange(raw_date.year, raw_date.month)[1]
        candidates = [
            raw_date + relativedelta(day=15),
            raw_date + relativedelta(day=month_last_day),
        ]
        previous_month = raw_date + relativedelta(months=-1)
        candidates.append(previous_month + relativedelta(day=monthrange(previous_month.year, previous_month.month)[1]))
        if raw_date.day > 15:
            candidates.append(raw_date + relativedelta(months=1, day=15))
        return min(candidates, key=lambda candidate: abs(candidate - raw_date))

    def action_compute_installments(self):
        for loan in self:
            loan._compute_installments()
        return True

    def _compute_installments(self):
        self.ensure_one()
        if self.installment_lines.filtered(lambda line: line.is_paid):
            raise UserError(_('No se pueden regenerar cuotas porque ya hay cuotas pagadas.'))
        commands = [Command.clear()]
        for index in range(self.term):
            installment_date = self._get_installment_date(index)
            interest_total = 0.0
            if self.is_apply_interest:
                if self.interest_type == 'reduce':
                    base = max(self.loan_amount - (self.installment_amount * index), 0.0)
                    interest_total = (base * self.interest_rate) / 100.0
                else:
                    interest_total = (self.loan_amount * self.interest_rate) / 100.0
            commands.append(Command.create({
                'name': '%s - %s' % (self.name or '/', index + 1),
                'employee_id': self.employee_id.id,
                'date': installment_date,
                'amount': self.loan_amount,
                'interest': interest_total,
                'installment_amt': self.installment_amount,
                'ins_interest': interest_total / self.term if self.term else 0.0,
                'tipo_deduccion': self.loan_type_id.tipo_deduccion,
            }))
        self.installment_lines = commands

    def action_send_request(self):
        for loan in self:
            loan.state = 'hr_approval'
            if not loan.installment_lines:
                loan._compute_installments()
        return True

    def hr_manager_approval_loan(self):
        return self.action_send_request()

    def paid_loan(self):
        for loan in self:
            if loan.loan_type_id.tipo_deduccion == '1' and loan.loan_type_id.journal_id and loan.loan_type_id.loan_account:
                loan._create_delivery_move()
            loan.state = 'paid'
        return True

    def _create_delivery_move(self):
        self.ensure_one()
        if self.move_id:
            return self.move_id
        if not self.employee_id.work_contact_id:
            raise UserError(_('Para generar el asiento de préstamo el empleado debe tener contacto de trabajo.'))
        if not self.loan_type_id.journal_id or not self.loan_type_id.loan_account:
            raise UserError(_('Configure diario y cuenta de préstamo en el tipo de préstamo.'))
        partner = self.employee_id.work_contact_id
        payable_account = partner.property_account_payable_id
        if not payable_account:
            raise UserError(_('El contacto del empleado no tiene cuenta por pagar configurada.'))
        move_lines = [
            Command.create({
                'account_id': self.loan_type_id.loan_account.id,
                'partner_id': partner.id,
                'name': self.name,
                'debit': self.loan_amount,
                'credit': 0.0,
            }),
            Command.create({
                'account_id': payable_account.id,
                'partner_id': partner.id,
                'name': self.name,
                'debit': 0.0,
                'credit': self.loan_amount,
            }),
        ]
        if self.interest_amount and self.loan_type_id.interest_account:
            move_lines.append(Command.create({
                'account_id': self.loan_type_id.interest_account.id,
                'partner_id': partner.id,
                'name': _('%s - Interés') % self.name,
                'debit': self.interest_amount,
                'credit': 0.0,
            }))
            move_lines.append(Command.create({
                'account_id': payable_account.id,
                'partner_id': partner.id,
                'name': _('%s - Interés') % self.name,
                'debit': 0.0,
                'credit': self.interest_amount,
            }))
        move = self.env['account.move'].create({
            'date': self.date,
            'ref': self.name,
            'journal_id': self.loan_type_id.journal_id.id,
            'company_id': self.company_id.id,
            'line_ids': move_lines,
        })
        self.move_id = move
        return move

    def action_done_loan(self):
        for loan in self:
            if not loan.installment_lines:
                loan._compute_installments()
            loan.state = 'done'
        return True

    def action_close_loan(self):
        self.write({'state': 'close'})
        return True

    def cancel_loan(self):
        self.write({'state': 'cancel'})
        return True

    def set_to_draft(self):
        self.write({'state': 'draft'})
        return True

    def hr_manager_reject_loan(self):
        self.write({'state': 'reject'})
        return True

    def view_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = vals.get('company_id') or self.env.company.id
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('employee.loan') or '/'
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = '/'
        default['state'] = 'draft'
        default['move_id'] = False
        return super().copy(default)

    def unlink(self):
        for loan in self:
            if loan.state != 'draft':
                raise ValidationError(_('El préstamo solo se puede eliminar en estado borrador.'))
        return super().unlink()
