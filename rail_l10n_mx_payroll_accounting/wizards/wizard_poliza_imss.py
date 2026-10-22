# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class WizardPolizaImss(models.TransientModel):
    _name = 'wizard.poliza.imss'
    _description = 'Póliza IMSS patronal'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date = fields.Date('Fecha contable', required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain="[('type', '=', 'general')]",
        check_company=True,
    )
    payslip_ids = fields.Many2many(
        'hr.payslip',
        string='Recibos',
        domain="[('state', 'in', ['validated', 'paid'])]",
        help='Opcional. Si se capturan códigos de reglas en las líneas, el wizard puede cargar importes desde estos recibos.',
    )
    line_ids = fields.One2many('wizard.poliza.imss.line', 'wizard_id', string='Conceptos')
    move_id = fields.Many2one('account.move', string='Asiento creado', readonly=True)
    total_amount = fields.Monetary('Total patronal', compute='_compute_total_amount', currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if 'line_ids' in fields_list:
            values['line_ids'] = self._get_default_line_commands(self.env.company)
        return values

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.line_ids.mapped('amount'))

    def action_reload_default_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.write({'line_ids': self._get_default_line_commands(self.company_id)})
        return self._reopen()

    def action_load_amounts_from_payslips(self):
        self.ensure_one()
        if not self.payslip_ids:
            raise UserError(_('Debe seleccionar recibos para cargar importes.'))
        for line in self.line_ids:
            codes = line._get_source_codes()
            if not codes:
                continue
            amount = sum(self.payslip_ids.mapped('line_ids').filtered(lambda l: l.code in codes).mapped('total'))
            line.amount = abs(amount)
        return self._reopen()

    def action_create_move(self):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        move_lines = []
        for line in self.line_ids.filtered(lambda l: not float_is_zero(l.amount, precision_digits=precision)):
            line._validate_accounts()
            move_lines.append((0, 0, {
                'name': line.name,
                'account_id': line.debit_account_id.id,
                'debit': line.amount,
                'credit': 0.0,
                'analytic_distribution': line.analytic_distribution,
            }))
            move_lines.append((0, 0, {
                'name': line.name,
                'account_id': line.credit_account_id.id,
                'debit': 0.0,
                'credit': line.amount,
                'analytic_distribution': line.analytic_distribution,
            }))
        if not move_lines:
            raise UserError(_('No hay importes para generar la póliza IMSS.'))
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'company_id': self.company_id.id,
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': _('Póliza IMSS patronal %s') % self.date,
            'line_ids': move_lines,
        })
        self.move_id = move.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }

    def _get_default_line_commands(self, company):
        concepts = [
            ('fixed_fee', 'Cuota fija patronal', company.rail_imss_fixed_fee_debit_account_id, company.rail_imss_fixed_fee_credit_account_id),
            ('excess', 'Excedente 3 UMA', company.rail_imss_excess_debit_account_id, company.rail_imss_excess_credit_account_id),
            ('cash_benefits', 'Prestaciones en dinero', company.rail_imss_cash_benefits_debit_account_id, company.rail_imss_cash_benefits_credit_account_id),
            ('medical_expenses', 'Gastos médicos pensionados', company.rail_imss_medical_expenses_debit_account_id, company.rail_imss_medical_expenses_credit_account_id),
            ('work_risk', 'Riesgo de trabajo', company.rail_imss_work_risk_debit_account_id, company.rail_imss_work_risk_credit_account_id),
            ('disability_life', 'Invalidez y vida', company.rail_imss_disability_life_debit_account_id, company.rail_imss_disability_life_credit_account_id),
            ('childcare', 'Guarderías y prestaciones sociales', company.rail_imss_childcare_debit_account_id, company.rail_imss_childcare_credit_account_id),
            ('retirement', 'Retiro', company.rail_imss_retirement_debit_account_id, company.rail_imss_retirement_credit_account_id),
            ('severance_old_age', 'Cesantía y vejez', company.rail_imss_severance_old_age_debit_account_id, company.rail_imss_severance_old_age_credit_account_id),
            ('infonavit', 'INFONAVIT patronal', company.rail_imss_infonavit_debit_account_id, company.rail_imss_infonavit_credit_account_id),
        ]
        return [(0, 0, {
            'concept': concept,
            'name': name,
            'debit_account_id': debit.id,
            'credit_account_id': credit.id,
        }) for concept, name, debit, credit in concepts]

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class WizardPolizaImssLine(models.TransientModel):
    _name = 'wizard.poliza.imss.line'
    _description = 'Línea póliza IMSS patronal'

    wizard_id = fields.Many2one('wizard.poliza.imss', required=True, ondelete='cascade')
    concept = fields.Selection([
        ('fixed_fee', 'Cuota fija patronal'),
        ('excess', 'Excedente 3 UMA'),
        ('cash_benefits', 'Prestaciones en dinero'),
        ('medical_expenses', 'Gastos médicos pensionados'),
        ('work_risk', 'Riesgo de trabajo'),
        ('disability_life', 'Invalidez y vida'),
        ('childcare', 'Guarderías y prestaciones sociales'),
        ('retirement', 'Retiro'),
        ('severance_old_age', 'Cesantía y vejez'),
        ('infonavit', 'INFONAVIT patronal'),
        ('other', 'Otro'),
    ], string='Concepto', required=True, default='other')
    name = fields.Char('Descripción', required=True)
    salary_rule_codes = fields.Char(
        'Códigos de reglas origen',
        help='Opcional. Separe con coma los códigos de líneas de nómina usados para cargar el importe desde recibos.',
    )
    amount = fields.Monetary('Importe', currency_field='currency_id')
    debit_account_id = fields.Many2one('account.account', string='Cuenta débito', required=True, check_company=True)
    credit_account_id = fields.Many2one('account.account', string='Cuenta crédito', required=True, check_company=True)
    analytic_distribution = fields.Json(string='Distribución analítica', groups='analytic.group_analytic_accounting')
    currency_id = fields.Many2one(related='wizard_id.currency_id')

    def _get_source_codes(self):
        self.ensure_one()
        return {code.strip() for code in (self.salary_rule_codes or '').split(',') if code.strip()}

    def _validate_accounts(self):
        self.ensure_one()
        if not self.debit_account_id or not self.credit_account_id:
            raise UserError(_('Debe configurar cuenta débito y crédito para %s.') % self.name)
        if self.debit_account_id.company_ids and self.wizard_id.company_id not in self.debit_account_id.company_ids:
            raise UserError(_('La cuenta débito de %s no pertenece a la compañía del wizard.') % self.name)
        if self.credit_account_id.company_ids and self.wizard_id.company_id not in self.credit_account_id.company_ids:
            raise UserError(_('La cuenta crédito de %s no pertenece a la compañía del wizard.') % self.name)
