# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    rail_installment_line_id = fields.Many2one(
        'installment.line',
        string='Cuota origen',
        ondelete='set null',
        copy=False,
    )
    rail_viaticos_id = fields.Many2one(
        'viaticos.nomina',
        string='Viático origen',
        ondelete='set null',
        copy=False,
    )
    rail_generated_by_extra = fields.Selection([
        ('loan', 'Préstamo/descuento'),
        ('viaticos', 'Viáticos'),
    ], string='Generado por extra MX', copy=False)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    rail_apply_installments = fields.Boolean(
        string='Aplicar préstamos/descuentos',
        default=True,
        help='Si está activo, al calcular se agregan las cuotas pendientes como inputs de nómina.',
    )
    installment_ids = fields.Many2many(
        'installment.line',
        'rail_payslip_installment_rel',
        'payslip_id',
        'installment_id',
        string='Préstamos/descuentos',
        copy=False,
    )
    installment_amount = fields.Float('Monto préstamo', compute='_compute_installment_amounts')
    installment_int = fields.Float('Interés préstamo', compute='_compute_installment_amounts')
    descuento1_amount = fields.Float('Monto descuento 1', compute='_compute_installment_amounts')
    descuento1_int = fields.Float('Interés descuento 1', compute='_compute_installment_amounts')
    descuento2_amount = fields.Float('Monto descuento 2', compute='_compute_installment_amounts')
    descuento2_int = fields.Float('Interés descuento 2', compute='_compute_installment_amounts')
    descuento3_amount = fields.Float('Monto descuento 3', compute='_compute_installment_amounts')
    descuento3_int = fields.Float('Interés descuento 3', compute='_compute_installment_amounts')
    descuento4_amount = fields.Float('Monto descuento 4', compute='_compute_installment_amounts')
    descuento4_int = fields.Float('Interés descuento 4', compute='_compute_installment_amounts')
    descuento5_amount = fields.Float('Monto descuento 5', compute='_compute_installment_amounts')
    descuento5_int = fields.Float('Interés descuento 5', compute='_compute_installment_amounts')
    descuento6_amount = fields.Float('Monto descuento 6', compute='_compute_installment_amounts')
    descuento6_int = fields.Float('Interés descuento 6', compute='_compute_installment_amounts')
    descuento7_amount = fields.Float('Monto descuento 7', compute='_compute_installment_amounts')
    descuento7_int = fields.Float('Interés descuento 7', compute='_compute_installment_amounts')
    descuento8_amount = fields.Float('Monto descuento 8', compute='_compute_installment_amounts')
    descuento8_int = fields.Float('Interés descuento 8', compute='_compute_installment_amounts')
    descuento9_amount = fields.Float('Monto descuento 9', compute='_compute_installment_amounts')
    descuento9_int = fields.Float('Interés descuento 9', compute='_compute_installment_amounts')
    descuento10_amount = fields.Float('Monto descuento 10', compute='_compute_installment_amounts')
    descuento10_int = fields.Float('Interés descuento 10', compute='_compute_installment_amounts')
    descuento11_amount = fields.Float('Monto descuento 11', compute='_compute_installment_amounts')
    descuento11_int = fields.Float('Interés descuento 11', compute='_compute_installment_amounts')
    descuento12_amount = fields.Float('Monto descuento 12', compute='_compute_installment_amounts')
    descuento12_int = fields.Float('Interés descuento 12', compute='_compute_installment_amounts')
    descuento13_amount = fields.Float('Monto descuento 13', compute='_compute_installment_amounts')
    descuento13_int = fields.Float('Interés descuento 13', compute='_compute_installment_amounts')
    descuento14_amount = fields.Float('Monto descuento 14', compute='_compute_installment_amounts')
    descuento14_int = fields.Float('Interés descuento 14', compute='_compute_installment_amounts')
    descuento15_amount = fields.Float('Monto descuento 15', compute='_compute_installment_amounts')
    descuento15_int = fields.Float('Interés descuento 15', compute='_compute_installment_amounts')
    rail_installment_total = fields.Float('Total cuotas', compute='_compute_installment_amounts')

    rail_viaticos_id = fields.Many2one(
        'viaticos.nomina',
        string='Viático origen',
        copy=False,
        ondelete='set null',
        index=True,
        tracking=True,
    )
    rail_viaticos_kind = fields.Selection([
        ('delivery', 'Entrega de viáticos'),
        ('check', 'Comprobación de viáticos'),
    ], string='Tipo de recibo de viáticos', copy=False, tracking=True)

    @api.depends('installment_ids.installment_amt', 'installment_ids.ins_interest', 'installment_ids.tipo_deduccion', 'installment_ids.is_skip')
    def _compute_installment_amounts(self):
        amount_fields = {str(index + 1): ('descuento%s_amount' % index, 'descuento%s_int' % index) for index in range(1, 16)}
        for slip in self:
            slip.installment_amount = 0.0
            slip.installment_int = 0.0
            slip.rail_installment_total = 0.0
            for amount_field, int_field in amount_fields.values():
                setattr(slip, amount_field, 0.0)
                setattr(slip, int_field, 0.0)
            for installment in slip.installment_ids.filtered(lambda line: not line.is_skip):
                amount = installment.installment_amt
                interest = installment.ins_interest
                slip.rail_installment_total += amount + interest
                if installment.tipo_deduccion == '1':
                    slip.installment_amount += amount
                    slip.installment_int += interest
                elif installment.tipo_deduccion in amount_fields:
                    amount_field, int_field = amount_fields[installment.tipo_deduccion]
                    setattr(slip, amount_field, getattr(slip, amount_field) + amount)
                    setattr(slip, int_field, getattr(slip, int_field) + interest)

    def _rail_get_installments_for_period(self):
        self.ensure_one()
        if self.rail_viaticos_id or not self.employee_id or not self.date_to:
            return self.env['installment.line']
        return self.env['installment.line'].search([
            ('employee_id', '=', self.employee_id.id),
            ('loan_id.state', 'in', ('paid', 'done')),
            ('is_paid', '=', False),
            ('is_skip', '=', False),
            ('date', '<=', self.date_to),
            ('payslip_id', '=', False),
        ], order='date, id')

    def _rail_remove_extra_inputs(self):
        for slip in self:
            removable = slip.input_line_ids.filtered(lambda line: line.rail_generated_by_extra == 'loan')
            if removable:
                slip.input_line_ids = [Command.unlink(line.id) for line in removable]

    def _rail_release_unpaid_installment_reservations(self):
        for slip in self:
            reservations = self.env['installment.line'].search([
                ('payslip_id', '=', slip.id),
                ('is_paid', '=', False),
            ])
            if reservations:
                reservations.write({'payslip_id': False})
            slip.installment_ids = [Command.clear()]

    def _rail_prepare_installment_input_commands(self, installments):
        self.ensure_one()
        commands = []
        for installment in installments:
            loan_type = installment.loan_id.loan_type_id
            input_type = loan_type.rail_get_default_input_type()
            if not input_type:
                raise UserError(_(
                    'No se encontró tipo de input para la deducción %(deduction)s del préstamo %(loan)s.'
                ) % {'deduction': installment.tipo_deduccion, 'loan': installment.loan_id.display_name})
            commands.append(Command.create({
                'name': installment.name or loan_type.name,
                'input_type_id': input_type.id,
                'amount': installment.installment_amt,
                'rail_installment_line_id': installment.id,
                'rail_generated_by_extra': 'loan',
            }))
            if installment.ins_interest:
                interest_input_type = loan_type.rail_get_interest_input_type()
                if not interest_input_type:
                    raise UserError(_('Configure un input de interés para el tipo de préstamo %s.') % loan_type.display_name)
                commands.append(Command.create({
                    'name': _('%s - Interés') % (installment.name or loan_type.name),
                    'input_type_id': interest_input_type.id,
                    'amount': installment.ins_interest,
                    'rail_installment_line_id': installment.id,
                    'rail_generated_by_extra': 'loan',
                }))
        return commands

    def rail_sync_installment_inputs(self):
        for slip in self:
            if slip.state != 'draft':
                continue

            # Libera cualquier reserva previa del mismo recibo antes de volver a calcular.
            slip._rail_release_unpaid_installment_reservations()
            slip._rail_remove_extra_inputs()

            if slip.rail_viaticos_id or not slip.rail_apply_installments:
                continue

            installments = slip._rail_get_installments_for_period()
            if installments:
                # La reserva se realiza en borrador para impedir que otro recibo tome la misma cuota.
                installments.write({'payslip_id': slip.id})
                slip.installment_ids = [Command.set(installments.ids)]
                commands = slip._rail_prepare_installment_input_commands(installments)
                if commands:
                    slip.input_line_ids = commands
        return True


    def rail_l10n_mx_compensation_seniority_years(self):
        self.ensure_one()
        first_date = (
            self.employee_id.sudo()._get_first_contract_date(no_gap=False)
            or self.version_id.contract_date_start
            or self.version_id.date_version
        )
        if not first_date or not self.date_to:
            return 1
        years = max((self.date_to - first_date).days / 365.0, 0.0)
        return max(int(round(years)), 1)

    def rail_l10n_mx_compensation_exempt_limit(self):
        self.ensure_one()
        uma = self._rule_parameter('l10n_mx_uma') or {}
        daily_uma = uma.get('daily', 0.0) if isinstance(uma, dict) else float(uma or 0.0)
        compensation_factor = float(self._rule_parameter('l10n_mx_compensation_factor') or 0.0)
        return daily_uma * self.rail_l10n_mx_compensation_seniority_years() * compensation_factor

    def compute_sheet(self):
        self.rail_sync_installment_inputs()
        return super().compute_sheet()

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            installments = self.env['installment.line'].search([
                ('payslip_id', '=', slip.id),
                ('is_skip', '=', False),
            ])
            if not installments:
                continue
            installments.write({'is_paid': True})
            slip.installment_ids = [Command.set(installments.ids)]
            for loan, loan_installments in installments.grouped('loan_id').items():
                loan.message_post(body=Markup(
                    '<p>Se pagaron %s cuota(s) mediante el recibo %s.</p>'
                ) % (len(loan_installments), slip._get_html_link()))
                active_lines = loan.installment_lines.filtered(lambda line: not line.is_skip)
                if active_lines and all(active_lines.mapped('is_paid')):
                    loan.state = 'close'
                elif loan.state == 'paid':
                    loan.state = 'done'
        return res

    def _rail_release_viaticos_links(self):
        for slip in self.filtered('rail_viaticos_id'):
            viatico = slip.rail_viaticos_id
            if slip.rail_viaticos_kind == 'delivery':
                lines = viatico.entregas_ids.filtered(lambda line: line.payslip_id == slip)
                lines.write({'generado': False, 'payslip_id': False})
                if viatico.delivery_payslip_id == slip:
                    viatico.delivery_payslip_id = False
                if not viatico.entregas_ids.filtered('generado') and not viatico.comprobaciones_ids.filtered('generado'):
                    viatico.state = 'draft'
            elif slip.rail_viaticos_kind == 'check':
                lines = viatico.comprobaciones_ids.filtered(lambda line: line.payslip_id == slip)
                lines.write({'generado': False, 'payslip_id': False})
                if viatico.check_payslip_id == slip:
                    viatico.check_payslip_id = False
                viatico.state = 'open'
            viatico.message_post(body=Markup(
                '<p>Se liberaron las líneas vinculadas al recibo cancelado/eliminado %s.</p>'
            ) % slip._get_html_link())

    def _rail_get_linked_installments(self):
        """Return every installment referenced by the payslip, including legacy/stale links.

        Older versions could leave the same installment in more than one draft payslip.  The
        direct ``payslip_id`` reservation is authoritative in the new flow, but the M2M and the
        generated inputs are also inspected so cancelling an old receipt can be repaired safely.
        """
        self.ensure_one()
        return (
            self.installment_ids
            | self.input_line_ids.rail_installment_line_id
            | self.env['installment.line'].search([('payslip_id', '=', self.id)])
        )

    def _rail_find_other_confirmed_installment_owner(self, installment):
        self.ensure_one()
        other_slips = self.env['hr.payslip'].search([
            ('id', '!=', self.id),
            ('state', 'in', ('validated', 'paid')),
            '|',
                ('installment_ids', 'in', [installment.id]),
                ('input_line_ids.rail_installment_line_id', '=', installment.id),
        ], order='date_to desc, id desc', limit=1)
        if installment.payslip_id and installment.payslip_id != self                 and installment.payslip_id.state in ('validated', 'paid'):
            other_slips |= installment.payslip_id
        return other_slips[:1]

    def action_payslip_cancel(self):
        installments_by_slip = {
            slip.id: slip._rail_get_linked_installments()
            for slip in self
        }
        loans = self.env['employee.loan'].browse()
        for installments in installments_by_slip.values():
            loans |= installments.loan_id
        states_before = {loan.id: loan.state for loan in loans}

        res = super().action_payslip_cancel()

        for slip in self:
            installments = installments_by_slip[slip.id]
            reverted = self.env['installment.line']
            kept_paid = self.env['installment.line']
            for installment in installments:
                other_owner = slip._rail_find_other_confirmed_installment_owner(installment)
                if other_owner:
                    # A confirmed/paid receipt still owns the installment.  Repair the direct
                    # reservation when the cancelled receipt was incorrectly stored as owner.
                    if installment.payslip_id == slip:
                        installment.payslip_id = other_owner.id
                    kept_paid |= installment
                    continue
                installment.write({'is_paid': False, 'payslip_id': False})
                reverted |= installment

            slip.installment_ids = [Command.clear()]
            for loan, loan_installments in installments.grouped('loan_id').items():
                previous_state = states_before.get(loan.id)
                # Cancelling payroll must never cancel the source loan.  Preserve the state that
                # existed before the inherited cancellation flow, and reopen a previously closed
                # loan when one of its payments was reverted.
                if loan.state == 'cancel' and previous_state != 'cancel':
                    loan.state = previous_state or 'done'
                if loan in reverted.loan_id and loan.state == 'close':
                    loan.state = 'done'

                reverted_for_loan = reverted.filtered(lambda line: line.loan_id == loan)
                kept_for_loan = kept_paid.filtered(lambda line: line.loan_id == loan)
                body = Markup(
                    '<p><strong>Cancelación de recibo de nómina</strong></p>'
                    '<ul>'
                    '<li>Recibo: %s</li>'
                    '<li>Cuotas revertidas: %s</li>'
                    '<li>Cuotas conservadas por otro recibo validado/pagado: %s</li>'
                    '<li>Estado del préstamo: %s</li>'
                    '</ul>'
                ) % (
                    slip._get_html_link(),
                    len(reverted_for_loan),
                    len(kept_for_loan),
                    dict(loan._fields['state'].selection).get(loan.state, loan.state),
                )
                loan.message_post(body=body)

        self._rail_release_viaticos_links()
        return res

    def unlink(self):
        draft_slips = self.filtered(lambda slip: slip.state in ('draft', 'cancel'))
        draft_slips._rail_release_unpaid_installment_reservations()
        draft_slips._rail_release_viaticos_links()
        return super().unlink()

    def action_rail_sync_installments(self):
        self.rail_sync_installment_inputs()
        return True
