# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .employee_loan_type import DEDUCTION_TYPE_SELECTION


class InstallmentLine(models.Model):
    _name = 'installment.line'
    _description = 'Cuota de préstamo/descuento'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date, name'

    name = fields.Char('Nombre', tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', index=True, tracking=True)
    loan_id = fields.Many2one(
        'employee.loan',
        string='Préstamo/descuento',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    date = fields.Date('Fecha', index=True, tracking=True)
    is_paid = fields.Boolean('Pagado', copy=False, index=True, tracking=True)
    amount = fields.Float('Monto original')
    interest = fields.Float('Interés total')
    ins_interest = fields.Float('Interés cuota')
    installment_amt = fields.Float('Cantidad a plazo')
    total_installment = fields.Float('Total cuota', compute='_compute_total_installment', store=True)
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Recibo de nómina',
        copy=False,
        ondelete='set null',
        tracking=True,
        help='También se usa para reservar la cuota mientras el recibo está en borrador.',
    )
    is_skip = fields.Boolean('Omitir cuota', copy=False, tracking=True)
    skip_reason = fields.Char('Motivo de omisión', tracking=True)
    skip_date = fields.Datetime('Fecha de omisión', copy=False, readonly=True)
    skip_user_id = fields.Many2one('res.users', string='Omitida por', copy=False, readonly=True)
    replacement_installment_id = fields.Many2one(
        'installment.line',
        string='Cuota reprogramada',
        copy=False,
        ondelete='set null',
        readonly=True,
    )
    skipped_from_id = fields.Many2one(
        'installment.line',
        string='Cuota original omitida',
        copy=False,
        ondelete='set null',
        readonly=True,
    )
    tipo_deduccion = fields.Selection(DEDUCTION_TYPE_SELECTION, string='Tipo de deducción')
    company_id = fields.Many2one(related='loan_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    @api.depends('installment_amt', 'ins_interest')
    def _compute_total_installment(self):
        for line in self:
            line.total_installment = line.installment_amt + line.ins_interest

    def _rail_post_skip_trace(self, action, reason=False, replacement=False):
        for line in self:
            if action == 'skip':
                body = Markup(
                    '<p><strong>Cuota omitida/reprogramada</strong></p>'
                    '<ul>'
                    '<li>Cuota: %s</li>'
                    '<li>Fecha original: %s</li>'
                    '<li>Motivo: %s</li>'
                    '<li>Usuario: %s</li>'
                    '<li>Nueva cuota: %s</li>'
                    '</ul>'
                ) % (
                    line.display_name,
                    line.date or '',
                    reason or _('Sin motivo indicado'),
                    self.env.user.display_name,
                    replacement.display_name if replacement else '',
                )
            else:
                body = Markup(
                    '<p><strong>Cuota reactivada</strong></p>'
                    '<ul>'
                    '<li>Cuota: %s</li>'
                    '<li>Usuario: %s</li>'
                    '</ul>'
                ) % (line.display_name, self.env.user.display_name)
            line.message_post(body=body)
            if line.loan_id:
                line.loan_id.message_post(body=body)

    def action_skip_installment(self):
        for line in self:
            if line.is_paid:
                raise UserError(_('No se puede omitir una cuota ya pagada.'))
            if line.payslip_id and line.payslip_id.state != 'cancel':
                raise UserError(_(
                    'La cuota %(line)s está reservada por el recibo %(payslip)s. '
                    'Quite la cuota del recibo o cancele el recibo antes de omitirla.'
                ) % {'line': line.display_name, 'payslip': line.payslip_id.display_name})
            if line.is_skip:
                continue

            loan = line.loan_id
            reason = line.skip_reason or _('Omitida manualmente desde el listado de cuotas')
            replacement = line.replacement_installment_id
            if not replacement:
                replacement_date = loan._get_installment_date(len(loan.installment_lines))
                replacement = self.create({
                    'name': _('%s - Reprogramada') % line.name,
                    'employee_id': line.employee_id.id,
                    'loan_id': loan.id,
                    'date': replacement_date,
                    'amount': line.amount,
                    'interest': line.interest,
                    'installment_amt': line.installment_amt,
                    'ins_interest': line.ins_interest,
                    'tipo_deduccion': line.tipo_deduccion,
                    'skipped_from_id': line.id,
                })
            line.write({
                'is_skip': True,
                'skip_reason': reason,
                'skip_date': fields.Datetime.now(),
                'skip_user_id': self.env.user.id,
                'replacement_installment_id': replacement.id,
                'payslip_id': False,
            })
            line._rail_post_skip_trace('skip', reason=reason, replacement=replacement)
        return True

    def action_unskip_installment(self):
        for line in self:
            if line.is_paid:
                raise UserError(_('No se puede reactivar una cuota ya pagada.'))
            replacement = line.replacement_installment_id
            if replacement:
                if replacement.is_paid:
                    raise UserError(_('No se puede reactivar la cuota porque su cuota reprogramada ya fue pagada.'))
                if replacement.payslip_id and replacement.payslip_id.state != 'cancel':
                    raise UserError(_(
                        'No se puede reactivar la cuota porque la cuota reprogramada está reservada por %s.'
                    ) % replacement.payslip_id.display_name)
                replacement.unlink()
            line.write({
                'is_skip': False,
                'skip_reason': False,
                'skip_date': False,
                'skip_user_id': False,
                'replacement_installment_id': False,
            })
            line._rail_post_skip_trace('unskip')
        return True

    def action_view_payslip(self):
        self.ensure_one()
        if not self.payslip_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'res_id': self.payslip_id.id,
            'view_mode': 'form',
        }
