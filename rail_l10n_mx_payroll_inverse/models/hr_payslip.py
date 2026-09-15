# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('version_id.wage', 'version_id.schedule_pay')
    def _compute_daily_salary(self):
        """Use the inverse candidate as a contractual monthly wage.

        The functional rule validated for MX is the same one used in the
        shared v18 localization: daily salary = monthly wage / configured
        days per month. The pay schedule is used later only to determine the
        amount corresponding to the payroll period.
        """
        super()._compute_daily_salary()
        for payslip in self:
            if not payslip.env.context.get('salary_simulation'):
                continue
            candidate = payslip.env.context.get('rail_inverse_candidate_wage')
            if candidate is None or not payslip.version_id:
                continue
            days_per_month = float(payslip._rule_parameter('l10n_mx_days_per_month') or 0.0)
            if days_per_month:
                payslip.l10n_mx_daily_salary = float(candidate or 0.0) / days_per_month

    def _get_paid_amount(self):
        """Return the simulated period salary from a monthly candidate wage.

        Core payroll shortcuts `_get_paid_amount()` to the contract wage while
        `salary_simulation` is active. For MX inverse payroll that would treat a
        monthly candidate as if it were weekly/quincenal/etc. We instead apply
        the configured Mexican schedule ratio, reproducing the validated v18
        behavior.
        """
        self.ensure_one()
        if not self.env.context.get('salary_simulation') or self.country_code != 'MX':
            return super()._get_paid_amount()
        candidate = self.env.context.get('rail_inverse_candidate_wage')
        if candidate is None or not self.version_id or self.version_id.wage_type == 'hourly':
            return super()._get_paid_amount()
        schedule_table = self._rule_parameter('l10n_mx_schedule_table') or {}
        schedule_days = schedule_table.get(self.version_id.schedule_pay) if isinstance(schedule_table, dict) else 0.0
        days_per_month = float(self._rule_parameter('l10n_mx_days_per_month') or 0.0)
        if not schedule_days or not days_per_month:
            return super()._get_paid_amount()

        start_date = max(self.date_from, self.version_id.contract_date_start or self.date_from)
        end_date = min(self.date_to, self.version_id.contract_date_end) if self.version_id.contract_date_end else self.date_to
        in_contract_days = max((end_date - start_date).days + 1, 0)
        actual_period_days = max((self.date_to - self.date_from).days + 1, 1)
        salary_factor = in_contract_days / actual_period_days
        daily_salary = float(candidate or 0.0) / days_per_month
        return daily_salary * float(schedule_days) * salary_factor

    @api.depends('l10n_mx_days_of_year', 'date_from', 'date_to', 'version_id')
    def _compute_integration_factor(self):
        """Compute the MX integration factor from the simulated hire date.

        The native Mexican method obtains seniority from
        ``employee._get_first_contract_date()``. That is correct for real
        employees, but it is not a reliable source for a prospective
        simulation: the technical employee/version only exists so salary
        rules can run and its version history is intentionally temporary.

        In that scenario Odoo could calculate ``l10n_mx_years_worked = 0``
        and then index ``l10n_mx_holiday_tables[0]``. The native table starts
        at year 1, producing ``KeyError(0)``.

        Only when ``salary_simulation`` is present do we use the explicit
        estimated hire date supplied by the inverse wizard. Normal payroll
        keeps the native implementation untouched.
        """
        if not self.env.context.get('salary_simulation'):
            return super()._compute_integration_factor()

        simulated_start = self.env.context.get('rail_inverse_contract_start_date')
        simulated_bonus_rate = self.env.context.get('rail_inverse_holiday_bonus_rate')

        for payslip in self:
            start_date = fields.Date.to_date(simulated_start) if simulated_start else False
            if not start_date:
                start_date = payslip.version_id.contract_date_start
            if not start_date:
                raise UserError(_(
                    'Indique la fecha estimada de ingreso para calcular el factor de integración.'
                ))
            if not payslip.date_to:
                raise UserError(_('La simulación requiere una fecha final de nómina.'))

            # For a prospective candidate the integration table always starts
            # at the first year of service. A future estimated hire date must
            # therefore not generate year 0 and index a non-existent table row.
            years_worked = payslip.date_to.year - start_date.year
            if start_date <= payslip.date_to + relativedelta(year=start_date.year):
                years_worked += 1
            years_worked = max(int(years_worked), 1)

            holiday_table = payslip._rule_parameter('l10n_mx_holiday_tables') or {}
            holidays_count = holiday_table.get(years_worked) if isinstance(holiday_table, dict) else False
            if holidays_count is None and isinstance(holiday_table, dict) and holiday_table:
                eligible = [year for year in holiday_table if year <= years_worked]
                if eligible:
                    holidays_count = holiday_table[max(eligible)]
            if holidays_count is None:
                raise UserError(_(
                    'No existe configuración de vacaciones para %(years)s año(s) de antigüedad '
                    'en l10n_mx_holiday_tables.'
                ) % {'years': years_worked})

            bonus_rate = (
                float(simulated_bonus_rate)
                if simulated_bonus_rate is not None
                else float(payslip.version_id.l10n_mx_holiday_bonus_rate or 0.0)
            )
            holiday_bonus_factor = float(holidays_count) * bonus_rate / 100.0
            number_of_days_year = payslip.l10n_mx_days_of_year
            if not number_of_days_year:
                raise UserError(_('No fue posible determinar los días del año para la simulación.'))

            payslip.l10n_mx_years_worked = years_worked
            payslip.l10n_mx_integration_factor = (
                holiday_bonus_factor
                + float(payslip._rule_parameter('l10n_mx_christmas_bonus') or 0.0)
                + number_of_days_year
            ) / number_of_days_year
