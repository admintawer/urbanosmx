# -*- coding: utf-8 -*-

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # Percepciones / beneficios custom que en v18 vivían en hr.contract.
    rail_productivity_bonus = fields.Boolean(string='Bono productividad', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_productivity_bonus_amount = fields.Monetary(string='Monto bono productividad', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_attendance_bonus = fields.Boolean(string='Bono asistencia', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_attendance_bonus_amount = fields.Monetary(string='Monto bono asistencia', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_punctuality_bonus = fields.Boolean(string='Bono puntualidad', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_punctuality_bonus_amount = fields.Monetary(string='Monto bono puntualidad', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_food_allowance = fields.Boolean(string='Alimentación', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_food_allowance_amount = fields.Monetary(string='Monto alimentación', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_additional_perception = fields.Boolean(string='Percepción adicional', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_additional_perception_amount = fields.Monetary(string='Monto percepción adicional', groups='hr_payroll.group_hr_payroll_user', tracking=True)

    # Deducciones custom conservadas como datos versionables.
    rail_alimony = fields.Boolean(string='Pensión alimenticia', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_alimony_fixed_amount = fields.Monetary(string='Monto fijo pensión alimenticia', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_savings_bank = fields.Boolean(string='Caja de ahorro', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_savings_bank_amount = fields.Monetary(string='Monto caja de ahorro', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_additional_deduction = fields.Boolean(string='Deducción adicional', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_additional_deduction_amount = fields.Monetary(string='Monto deducción adicional', groups='hr_payroll.group_hr_payroll_user', tracking=True)

    # Parámetros operativos usados por módulos posteriores.
    rail_payment_type = fields.Selection([
        ('cash', 'Efectivo'),
        ('transfer', 'Transferencia'),
        ('check', 'Cheque'),
        ('other', 'Otro'),
    ], string='Tipo de pago legacy', groups='hr_payroll.group_hr_payroll_user', tracking=True,
       help='Campo puente para migrar el tipo de pago utilizado por layouts v18. No sustituye la cuenta bancaria nativa.')
    rail_vacation_bonus_type = fields.Selection([
        ('fixed', 'Fijo'),
        ('percentage', 'Porcentaje'),
    ], string='Tipo prima vacacional legacy', groups='hr_payroll.group_hr_payroll_user', tracking=True)

    rail_seventh_day = fields.Boolean(string='Séptimo día', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_seventh_day_disability = fields.Boolean(string='Incapacidad afecta séptimo día', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_seventh_day_discount = fields.Boolean(string='Descuento séptimo día', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_english_week = fields.Boolean(string='Semana inglesa', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_sunday_bonus = fields.Boolean(string='Prima dominical', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_extra_isr_calculation = fields.Boolean(string='Calcular ISR extra', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_advanced_vacations = fields.Boolean(string='Vacaciones adelantadas', groups='hr_payroll.group_hr_payroll_user', tracking=True)

    # Único SBC autoritativo. Consolida sueldo_base_cotizacion y sbc_fijo de v18.
    rail_fixed_sbc = fields.Float(
        string='Sueldo base de cotización (IMSS)',
        digits='Payroll',
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
        help=(
            'SBC vigente de la versión laboral. Consolida los campos '
            'sueldo_base_cotizacion y sbc_fijo de v18. Se calcula desde el salario, '
            'la antigüedad, vacaciones, prima vacacional, aguinaldo y el tope IMSS; '
            'el cálculo SBC bimestral puede actualizarlo con la parte variable.'
        ),
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        fields_list = super()._get_whitelist_fields_from_template() or []
        fields_list += [
            'rail_productivity_bonus',
            'rail_productivity_bonus_amount',
            'rail_attendance_bonus',
            'rail_attendance_bonus_amount',
            'rail_punctuality_bonus',
            'rail_punctuality_bonus_amount',
            'rail_food_allowance',
            'rail_food_allowance_amount',
            'rail_additional_perception',
            'rail_additional_perception_amount',
            'rail_alimony',
            'rail_alimony_fixed_amount',
            'rail_savings_bank',
            'rail_savings_bank_amount',
            'rail_additional_deduction',
            'rail_additional_deduction_amount',
            'rail_payment_type',
            'rail_vacation_bonus_type',
            'rail_seventh_day',
            'rail_seventh_day_disability',
            'rail_seventh_day_discount',
            'rail_english_week',
            'rail_sunday_bonus',
            'rail_extra_isr_calculation',
            'rail_advanced_vacations',
            'rail_fixed_sbc',
        ]
        return fields_list

    def _rail_is_mexican_version(self):
        self.ensure_one()
        company = self.company_id or self.employee_id.company_id
        return bool(company and company.country_id.code == 'MX')

    def _rail_get_sbc_reference_date(self, reference_date=None):
        self.ensure_one()
        return fields.Date.to_date(
            reference_date or self.date_version or self.contract_date_start or fields.Date.today()
        )

    def _rail_get_rule_parameter(self, code, reference_date, raise_if_not_found=False):
        self.ensure_one()
        return self.env['hr.rule.parameter']._get_parameter_from_code(
            code,
            reference_date,
            raise_if_not_found=raise_if_not_found,
        )

    def _rail_get_first_contract_date_for_sbc(self, reference_date):
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return self.contract_date_start or self.date_version
        first_date = (
            employee.with_context(before_date=reference_date)._get_first_contract_date()
            or employee._get_first_contract_date()
        )
        return first_date or self.contract_date_start or self.date_version

    def _rail_get_sbc_calculation_details(self, reference_date=None, wage=None, raise_if_not_found=False):
        """Return the native-v19-based fixed SBC calculation details.

        This mirrors the Mexican localization logic used by ``hr.payslip`` for
        daily salary and integration factor, then applies the native IMSS limit
        expressed as daily UMA multiples. It does not include the variable
        bimonthly component; that component is calculated in the IMSS module.
        """
        self.ensure_one()
        reference_date = self._rail_get_sbc_reference_date(reference_date)
        empty = {
            'reference_date': reference_date,
            'first_contract_date': False,
            'seniority_years': 0,
            'schedule_days': 0.0,
            'daily_wage': 0.0,
            'vacation_days': 0.0,
            'holiday_bonus_rate': self.l10n_mx_holiday_bonus_rate or 0.0,
            'christmas_bonus_days': 0.0,
            'days_of_year': 0,
            'integration_factor': 0.0,
            'uncapped_sbc': 0.0,
            'max_sbc': 0.0,
            'sbc': 0.0,
        }
        if not self.employee_id or not self._rail_is_mexican_version():
            return empty

        wage_value = self.wage if wage is None else float(wage or 0.0)
        if wage_value <= 0.0 or not self.schedule_pay:
            return empty

        schedule_table = self._rail_get_rule_parameter(
            'l10n_mx_schedule_table', reference_date, raise_if_not_found
        ) or {}
        schedule_days = schedule_table.get(self.schedule_pay)
        if not schedule_days:
            if raise_if_not_found:
                raise UserError(_(
                    'No existe un número de días configurado para la periodicidad %(schedule)s '
                    'en el parámetro l10n_mx_schedule_table.'
                ) % {'schedule': self.schedule_pay})
            return empty

        first_contract_date = self._rail_get_first_contract_date_for_sbc(reference_date)
        if not first_contract_date:
            if raise_if_not_found:
                raise UserError(_('La versión laboral no tiene una fecha inicial de antigüedad.'))
            return empty

        seniority_years = reference_date.year - first_contract_date.year
        if first_contract_date <= reference_date + relativedelta(year=first_contract_date.year):
            seniority_years += 1
        seniority_years = max(seniority_years, 1)

        holiday_table = self._rail_get_rule_parameter(
            'l10n_mx_holiday_tables', reference_date, raise_if_not_found
        ) or {}
        vacation_days = holiday_table.get(seniority_years)
        if vacation_days is None and holiday_table:
            eligible_years = [year for year in holiday_table if year <= seniority_years]
            if eligible_years:
                vacation_days = holiday_table[max(eligible_years)]
        if vacation_days is None:
            if raise_if_not_found:
                raise UserError(_(
                    'No existe una fila de vacaciones para %(years)s año(s) de antigüedad.'
                ) % {'years': seniority_years})
            return empty

        christmas_bonus_days = self._rail_get_rule_parameter(
            'l10n_mx_christmas_bonus', reference_date, raise_if_not_found
        ) or 0.0
        uma = self._rail_get_rule_parameter(
            'l10n_mx_uma', reference_date, raise_if_not_found
        ) or {}
        imss_limit = self._rail_get_rule_parameter(
            'l10n_mx_imss_limit_with_uma', reference_date, raise_if_not_found
        ) or 25.0
        daily_uma = uma.get('daily', 0.0) if isinstance(uma, dict) else float(uma or 0.0)

        days_of_year = (date(reference_date.year, 12, 31) - date(reference_date.year, 1, 1)).days + 1
        holiday_bonus_rate = (self.l10n_mx_holiday_bonus_rate or 0.0) / 100.0
        integration_factor = (
            days_of_year
            + float(christmas_bonus_days)
            + float(vacation_days) * holiday_bonus_rate
        ) / days_of_year
        daily_wage = wage_value / float(schedule_days)
        uncapped_sbc = daily_wage * integration_factor
        max_sbc = daily_uma * float(imss_limit) if daily_uma else 0.0
        sbc = min(uncapped_sbc, max_sbc) if max_sbc else uncapped_sbc

        return {
            'reference_date': reference_date,
            'first_contract_date': first_contract_date,
            'seniority_years': seniority_years,
            'schedule_days': float(schedule_days),
            'daily_wage': daily_wage,
            'vacation_days': float(vacation_days),
            'holiday_bonus_rate': self.l10n_mx_holiday_bonus_rate or 0.0,
            'christmas_bonus_days': float(christmas_bonus_days),
            'days_of_year': days_of_year,
            'integration_factor': integration_factor,
            'uncapped_sbc': uncapped_sbc,
            'max_sbc': max_sbc,
            'sbc': round(sbc, 4),
        }

    def _rail_calculate_base_sbc(self, reference_date=None, wage=None, raise_if_not_found=False):
        self.ensure_one()
        return self._rail_get_sbc_calculation_details(
            reference_date=reference_date,
            wage=wage,
            raise_if_not_found=raise_if_not_found,
        )['sbc']

    def _rail_set_calculated_sbc(self, reference_date=None):
        for version in self:
            calculated_sbc = version._rail_calculate_base_sbc(reference_date=reference_date)
            if calculated_sbc:
                version.with_context(
                    rail_skip_sbc_autocalculate=True,
                    rail_skip_imss_auto_incidence=True,
                    tracking_disable=True,
                ).write({'rail_fixed_sbc': calculated_sbc})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        versions = super().create(vals_list)
        if self.env.context.get('rail_skip_sbc_autocalculate'):
            return versions
        for version, vals in zip(versions, vals_list):
            if version.employee_id and not vals.get('rail_fixed_sbc') and not version.rail_fixed_sbc:
                version._rail_set_calculated_sbc(reference_date=version.date_version)
        return versions

    def write(self, vals):
        watched_fields = {
            'wage', 'schedule_pay', 'l10n_mx_holiday_bonus_rate',
            'contract_date_start', 'date_version', 'employee_id',
        }
        must_recalculate = (
            not self.env.context.get('rail_skip_sbc_autocalculate')
            and 'rail_fixed_sbc' not in vals
            and bool(watched_fields.intersection(vals))
        )
        result = super().write(vals)
        if must_recalculate:
            for version in self:
                version._rail_set_calculated_sbc(reference_date=version.date_version)
        return result

    @api.onchange('wage', 'schedule_pay', 'l10n_mx_holiday_bonus_rate', 'contract_date_start', 'date_version')
    def _onchange_rail_calculate_sbc(self):
        for version in self:
            if version.employee_id and version._rail_is_mexican_version():
                calculated_sbc = version._rail_calculate_base_sbc(reference_date=version.date_version)
                if calculated_sbc:
                    version.rail_fixed_sbc = calculated_sbc

    @api.model
    def _rail_backfill_missing_sbc(self):
        versions = self.with_context(active_test=False).search([
            ('employee_id', '!=', False),
            ('rail_fixed_sbc', '<=', 0),
        ])
        for version in versions:
            version._rail_set_calculated_sbc(reference_date=version.date_version)
        return True

    def rail_create_new_version(self, effective_date, values=None):
        """Create a new employee version using Odoo 19 native versioning."""
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Solo se puede crear una nueva versión para una versión asociada a un empleado.'))
        if not effective_date:
            raise UserError(_('La fecha efectiva es obligatoria para crear una nueva versión.'))
        vals = dict(values or {})
        vals['date_version'] = effective_date

        # create_version copies whitelisted values from the previous version. If
        # the wage changes, force the copied SBC to zero so create() recalculates
        # it from the new salary. Explicit SBC values (e.g. bimonthly result) win.
        wage_field = self._get_contract_wage_field()
        if wage_field in vals and 'rail_fixed_sbc' not in vals:
            vals['rail_fixed_sbc'] = 0.0
        return self.employee_id.create_version(vals)
