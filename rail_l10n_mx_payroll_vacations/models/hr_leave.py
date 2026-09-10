# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    rail_is_vacation_leave = fields.Boolean(
        string='Es vacaciones MX',
        compute='_compute_rail_is_vacation_leave',
    )
    rail_vacation_available_days = fields.Float(
        string='Días vacaciones disponibles MX',
        compute='_compute_rail_vacation_available_days',
        digits='Payroll',
    )
    rail_vacation_line_id = fields.Many2one(
        'rail.vacation.line',
        string='Año de vacaciones a consumir',
        domain="[('employee_id', '=', employee_id), ('state', '=', 'active'), ('remaining_days', '>', 0)]",
        help='Opcional. Si se deja vacío, se consumirán primero los años activos más antiguos.',
    )
    rail_vacation_consumption_ids = fields.One2many(
        'rail.vacation.leave.consumption',
        'leave_id',
        string='Consumo vacaciones MX',
        readonly=True,
        copy=False,
    )
    rail_vacation_advanced_days = fields.Float(
        string='Días adelantados MX',
        digits='Payroll',
        readonly=True,
        copy=False,
    )

    @api.depends('holiday_status_id', 'holiday_status_id.code', 'holiday_status_id.rail_is_vacation')
    def _compute_rail_is_vacation_leave(self):
        for leave in self:
            leave.rail_is_vacation_leave = leave._rail_is_vacation_request()

    @api.depends('employee_id', 'holiday_status_id', 'request_date_from', 'date_from', 'rail_vacation_line_id')
    def _compute_rail_vacation_available_days(self):
        for leave in self:
            leave.rail_vacation_available_days = leave._rail_get_available_vacation_days()

    def _rail_is_vacation_request(self):
        self.ensure_one()
        leave_type = self.holiday_status_id
        return bool(leave_type and (leave_type.rail_is_vacation or leave_type.code == 'VAC'))

    def _rail_get_effective_date(self):
        self.ensure_one()
        if self.request_date_from:
            return self.request_date_from
        if self.date_from:
            return self.date_from.date()
        return fields.Date.context_today(self)

    def _rail_get_leave_version(self):
        self.ensure_one()
        if not self.employee_id:
            return self.env['hr.version']
        return self.employee_id.sudo()._get_version(self._rail_get_effective_date())

    def _rail_get_vacation_lines(self):
        self.ensure_one()
        version = self._rail_get_leave_version()
        if not version:
            return self.env['rail.vacation.line']
        lines = version.rail_vacation_line_ids.filtered(lambda l: l.state == 'active' and l.remaining_days > 0)
        if self.rail_vacation_line_id:
            return self.rail_vacation_line_id
        return lines.sorted(lambda l: (l.year or '', l.id))

    def _rail_get_available_vacation_days(self):
        self.ensure_one()
        if not self.employee_id or not self._rail_is_vacation_request():
            return 0.0
        return sum(self._rail_get_vacation_lines().mapped('remaining_days'))

    def _rail_get_requested_days(self):
        self.ensure_one()
        return self.number_of_days or 0.0

    def _rail_check_vacation_balance(self):
        for leave in self:
            if not leave._rail_is_vacation_request() or leave.rail_vacation_consumption_ids or leave.rail_vacation_advanced_days:
                continue
            days = leave._rail_get_requested_days()
            if float_is_zero(days, precision_digits=2):
                continue
            version = leave._rail_get_leave_version()
            if not version:
                raise UserError(_('No se encontró una versión laboral para %(employee)s.', employee=leave.employee_id.name))
            available = leave._rail_get_available_vacation_days()
            if float_compare(days, available, precision_digits=2) > 0 and not version.rail_advanced_vacations:
                raise UserError(_(
                    '%(employee)s no tiene suficientes días de vacaciones. Solicitado: %(requested)s, disponible: %(available)s.',
                    employee=leave.employee_id.name,
                    requested=days,
                    available=available,
                ))
            if leave.rail_vacation_line_id and float_compare(days, leave.rail_vacation_line_id.remaining_days, precision_digits=2) > 0 and not version.rail_advanced_vacations:
                raise UserError(_(
                    'La línea %(line)s no tiene suficientes días disponibles para esta solicitud.',
                    line=leave.rail_vacation_line_id.display_name,
                ))

    def _rail_consume_vacation_days(self):
        Consumption = self.env['rail.vacation.leave.consumption'].sudo()
        for leave in self.sudo():
            if not leave._rail_is_vacation_request() or leave.state != 'validate':
                continue
            if leave.rail_vacation_consumption_ids or leave.rail_vacation_advanced_days:
                continue
            remaining_to_consume = leave._rail_get_requested_days()
            if float_is_zero(remaining_to_consume, precision_digits=2):
                continue
            version = leave._rail_get_leave_version().sudo()
            lines = leave._rail_get_vacation_lines().sudo()
            for line in lines:
                if float_compare(remaining_to_consume, 0.0, precision_digits=2) <= 0:
                    break
                available = line.remaining_days
                if float_compare(available, 0.0, precision_digits=2) <= 0:
                    continue
                days = min(remaining_to_consume, available)
                line.write({'used_days': line.used_days + days})
                Consumption.create({
                    'leave_id': leave.id,
                    'vacation_line_id': line.id,
                    'days': days,
                })
                remaining_to_consume -= days

            if float_compare(remaining_to_consume, 0.0, precision_digits=2) > 0:
                if not version.rail_advanced_vacations:
                    raise UserError(_('No hay saldo suficiente para consumir vacaciones.'))
                version.rail_vacation_advance_days += remaining_to_consume
                leave.rail_vacation_advanced_days = remaining_to_consume

    def _rail_restore_vacation_days(self):
        for leave in self.sudo():
            if not leave.rail_vacation_consumption_ids and not leave.rail_vacation_advanced_days:
                continue
            for consumption in leave.rail_vacation_consumption_ids:
                line = consumption.vacation_line_id
                line.used_days = max((line.used_days or 0.0) - (consumption.days or 0.0), 0.0)
            leave.rail_vacation_consumption_ids.unlink()
            if leave.rail_vacation_advanced_days:
                version = leave._rail_get_leave_version().sudo()
                version.rail_vacation_advance_days = max((version.rail_vacation_advance_days or 0.0) - leave.rail_vacation_advanced_days, 0.0)
                leave.rail_vacation_advanced_days = 0.0

    def _action_validate(self, check_state=True):
        self._rail_check_vacation_balance()
        res = super()._action_validate(check_state=check_state)
        self._rail_consume_vacation_days()
        return res

    def write(self, vals):
        states_before = {leave.id: leave.state for leave in self}
        res = super().write(vals)
        if 'state' in vals:
            to_restore = self.filtered(lambda leave: states_before.get(leave.id) == 'validate' and leave.state in ('refuse', 'cancel'))
            to_restore._rail_restore_vacation_days()
        return res

    def unlink(self):
        self._rail_restore_vacation_days()
        return super().unlink()

    @api.onchange('employee_id', 'holiday_status_id', 'request_date_from', 'request_date_to', 'rail_vacation_line_id')
    def _onchange_rail_vacation_balance(self):
        for leave in self:
            if not leave.employee_id or not leave._rail_is_vacation_request():
                continue
            days = leave._rail_get_requested_days()
            available = leave._rail_get_available_vacation_days()
            version = leave._rail_get_leave_version()
            if days and float_compare(days, available, precision_digits=2) > 0 and not version.rail_advanced_vacations:
                raise UserError(_(
                    '%(employee)s no tiene suficientes días de vacaciones. Solicitado: %(requested)s, disponible: %(available)s.',
                    employee=leave.employee_id.name,
                    requested=days,
                    available=available,
                ))
