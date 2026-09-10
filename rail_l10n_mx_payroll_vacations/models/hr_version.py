# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class HrVersion(models.Model):
    _inherit = 'hr.version'

    rail_vacation_line_ids = fields.One2many(
        'rail.vacation.line',
        'version_id',
        string='Saldos vacacionales MX',
        groups='hr_holidays.group_hr_holidays_user',
    )
    rail_vacation_available_days = fields.Float(
        string='Días vacaciones disponibles MX',
        compute='_compute_rail_vacation_available_days',
        digits='Payroll',
        groups='hr_holidays.group_hr_holidays_user',
    )
    rail_vacation_advance_days = fields.Float(
        string='Vacaciones adelantadas MX',
        digits='Payroll',
        default=0.0,
        groups='hr_holidays.group_hr_holidays_user',
        tracking=True,
    )
    rail_seniority_start_date = fields.Date(
        string='Fecha inicial de antigüedad',
        compute='_compute_rail_seniority',
        groups='hr_holidays.group_hr_holidays_user',
        help='Primera fecha de contrato registrada para el empleado, considerando todas sus versiones laborales.',
    )
    rail_seniority_years = fields.Integer(
        string='Años de antigüedad',
        compute='_compute_rail_seniority',
        groups='hr_holidays.group_hr_holidays_user',
        help='Años completos transcurridos desde el primer contrato del empleado.',
    )

    @api.depends('rail_vacation_line_ids.remaining_days', 'rail_vacation_line_ids.state')
    def _compute_rail_vacation_available_days(self):
        for version in self:
            version.rail_vacation_available_days = sum(
                version.rail_vacation_line_ids.filtered(lambda line: line.state == 'active').mapped('remaining_days')
            )

    @api.depends('employee_id', 'employee_id.version_ids.contract_date_start')
    def _compute_rail_seniority(self):
        today = fields.Date.context_today(self)
        for version in self:
            start_date = version._rail_get_seniority_start_date()
            version.rail_seniority_start_date = start_date
            version.rail_seniority_years = (
                max(relativedelta(today, start_date).years, 0)
                if start_date
                else 0
            )

    def _rail_get_seniority_start_date(self):
        """Return the employee's first contract date across all hr.version rows.

        The functional requirement is to preserve seniority from the first
        contract even when later contracts/versions start on a newer date.
        Odoo 19 already exposes this helper on hr.employee; no_gap=False makes
        the lookup explicitly consider the first historical contract record.
        """
        self.ensure_one()
        if not self.employee_id:
            return False
        return self.employee_id.sudo()._get_first_contract_date(no_gap=False)

    def _rail_get_years_worked(self, as_of_date):
        self.ensure_one()
        start_date = self._rail_get_seniority_start_date()
        if not start_date or not as_of_date:
            return 0
        years = relativedelta(fields.Date.to_date(as_of_date), start_date).years
        return max(years, 0)

    def _rail_get_anniversary_date(self, as_of_date):
        self.ensure_one()
        start_date = self._rail_get_seniority_start_date()
        years = self._rail_get_years_worked(as_of_date)
        return start_date + relativedelta(years=years) if start_date and years > 0 else False

    @api.model
    def _cron_rail_generate_vacation_anniversaries(self):
        """Generate balances on the anniversary of the first contract.

        The previous implementation used the current version's contract start,
        which reset seniority whenever a new hr.version/contract was created.
        """
        today = fields.Date.context_today(self)
        employees = self.env['hr.employee'].search([
            ('version_ids.contract_date_start', '!=', False),
        ])
        for employee in employees:
            start_date = employee.sudo()._get_first_contract_date(no_gap=False)
            if not start_date:
                continue
            years = max(relativedelta(today, start_date).years, 0)
            anniversary_date = start_date + relativedelta(years=years) if years else False
            if anniversary_date != today:
                continue

            version = employee.sudo()._get_version(today)
            if not version or not version._is_in_contract(today):
                continue
            try:
                version.rail_generate_vacation_line_for_date(
                    today,
                    raise_if_exists=False,
                    update_existing=False,
                )
            except UserError:
                # The cron must not block payroll/time-off operations. Manual
                # recalculation surfaces the precise functional error.
                continue
        return True

    def _rail_get_vacation_days_from_mx_parameter(self, as_of_date):
        self.ensure_one()
        years = self._rail_get_years_worked(as_of_date)
        if years <= 0:
            return 0.0
        table = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_mx_holiday_tables',
            fields.Date.to_date(as_of_date),
            raise_if_not_found=False,
        ) or {}
        if not table:
            raise UserError(_('No se encontró el parámetro nativo l10n_mx_holiday_tables para calcular vacaciones.'))
        if years in table:
            return float(table[years])
        max_year = max(table.keys())
        return float(table[max_year])

    def rail_generate_vacation_line_for_date(
        self,
        as_of_date=None,
        raise_if_exists=True,
        update_existing=False,
    ):
        self.ensure_one()
        as_of_date = fields.Date.to_date(as_of_date or fields.Date.context_today(self))
        if not self.employee_id:
            raise UserError(_('La versión debe pertenecer a un empleado.'))

        seniority_start = self._rail_get_seniority_start_date()
        if not seniority_start:
            raise UserError(_('El empleado no tiene una fecha inicial de contrato para calcular su antigüedad.'))

        years = self._rail_get_years_worked(as_of_date)
        if years <= 0:
            raise UserError(_('El empleado aún no cumple un año laboral en la fecha indicada.'))

        anniversary_date = self._rail_get_anniversary_date(as_of_date)
        year = str(anniversary_date.year)
        existing = self.rail_vacation_line_ids.filtered(
            lambda line: line.anniversary_date == anniversary_date
            or (not line.anniversary_date and line.year == year)
        )[:1]

        days = self._rail_get_vacation_days_from_mx_parameter(as_of_date)
        if float_is_zero(days, precision_digits=2):
            raise UserError(_(
                'El parámetro nativo de vacaciones devolvió cero días para %(employee)s.',
                employee=self.employee_id.name,
            ))

        values = {
            'year': year,
            'seniority_start_date': seniority_start,
            'seniority_years': years,
            'anniversary_date': anniversary_date,
            'granted_days': days,
            'state': 'active',
            'note': _(
                'Calculado con l10n_mx_holiday_tables al %(date)s. '
                'Antigüedad tomada desde el primer contrato: %(start)s (%(years)s años).',
                date=as_of_date,
                start=seniority_start,
                years=years,
            ),
        }

        if existing:
            if update_existing:
                if float_compare(existing.used_days, days, precision_digits=2) > 0:
                    raise UserError(_(
                        'No se puede recalcular el saldo de %(employee)s: los días usados '
                        '(%(used)s) exceden los días que corresponden por antigüedad (%(granted)s).',
                        employee=self.employee_id.name,
                        used=existing.used_days,
                        granted=days,
                    ))
                existing.write(values)
                return existing
            if raise_if_exists:
                raise UserError(_(
                    'Ya existe saldo vacacional para el aniversario %(date)s.',
                    date=anniversary_date,
                ))
            return existing

        return self.env['rail.vacation.line'].create({
            'version_id': self.id,
            'used_days': 0.0,
            'origin': 'auto',
            **values,
        })

    def _rail_copy_vacation_lines_to(self, new_version):
        self.ensure_one()
        if not new_version or new_version == self or new_version.rail_vacation_line_ids:
            return
        for line in self.rail_vacation_line_ids:
            line.copy({
                'version_id': new_version.id,
                'origin': 'migration',
                'note': _(
                    'Copiado desde la versión laboral %(version)s al crear una nueva versión.\n%(note)s',
                    version=self.display_name,
                    note=line.note or '',
                ),
            })
        if self.rail_vacation_advance_days and not new_version.rail_vacation_advance_days:
            new_version.rail_vacation_advance_days = self.rail_vacation_advance_days

    def rail_create_new_version(self, effective_date, values=None):
        self.ensure_one()
        new_version = super().rail_create_new_version(effective_date, values=values)
        if new_version and new_version != self:
            self._rail_copy_vacation_lines_to(new_version)
        return new_version
