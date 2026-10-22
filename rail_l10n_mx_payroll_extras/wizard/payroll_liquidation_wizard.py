# -*- coding: utf-8 -*-

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError


class PayrollLiquidationWizard(models.TransientModel):
    _name = 'calculo.liquidaciones'
    _description = 'Cálculo de liquidaciones'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    version_id = fields.Many2one(
        'hr.version',
        string='Versión laboral',
        domain="[('employee_id', '=', employee_id)]",
    )
    fecha_inicio = fields.Date(string='Fecha inicio último periodo', required=True)
    fecha_liquidacion = fields.Date(string='Fecha liquidación', required=True, default=fields.Date.context_today)

    tipo_de_baja = fields.Selection([
        ('01', 'Separación voluntaria'),
        ('02', 'Baja'),
    ], string='Tipo de baja', required=True, default='01')

    dias_base = fields.Float('Días base', default=90.0)
    dias_x_ano = fields.Float('Días por cada año trabajado', default=20.0)
    dias_totales = fields.Float('Total de días')
    indemnizacion = fields.Boolean('Pagar indemnización')
    antiguedad = fields.Boolean('Pagar antigüedad')
    round_antiguedad = fields.Boolean('Redondear antigüedad')
    antiguedad_anos = fields.Float('Antigüedad')

    dias_pendientes_pagar = fields.Float('Días de nómina a pagar')
    dias_vacaciones = fields.Float('Días de vacaciones')
    dias_aguinaldo = fields.Float('Días aguinaldo')
    dias_prima_vac = fields.Float('Días prima vacacional')
    prima_vac = fields.Float('Prima vacacional (%)')
    fondo_ahorro = fields.Float(
        'Fondo ahorro',
        help=(
            'En v18 se calculaba con códigos configurados en tablas.cfdi. Ese origen ya no existe '
            'en v19; el valor queda editable para no inventar una equivalencia.'
        ),
    )
    pago_separacion = fields.Float('Pago por separación')

    monto_prima_antiguedad = fields.Float('Prima antigüedad')
    monto_indemnizacion = fields.Float('Indemnización')
    sueldo_calculo = fields.Selection([
        ('01', 'Sueldo diario'),
        ('02', 'Sueldo diario integrado'),
    ], string='Sueldo para cálculos', default='01', required=True)
    sueldo_calculo_monto = fields.Float('Sueldo cálculo monto')
    tope_prima = fields.Selection([
        ('01', 'Salario mínimo'),
        ('02', 'UMA'),
    ], string='Para cálculo topado usar', default='01', required=True)
    tope_prima_monto = fields.Float('Tope prima monto')

    estructura = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura ordinaria',
        domain="[('country_id.code', '=', 'MX')]",
    )
    estructura_extra = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura indemnización / finiquito',
        domain="[('country_id.code', '=', 'MX')]",
        help='La estructura estándar de liquidación MX se instala con este módulo y se precarga automáticamente.',
    )
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Procesamiento')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('created', 'Recibos creados'),
    ], default='draft')
    generated_payslip_ids = fields.Many2many('hr.payslip', string='Recibos generados', readonly=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'hr.employee' and active_id and 'employee_id' in field_list:
            values['employee_id'] = active_id
        if 'estructura_extra' in field_list:
            structure = self.env.ref('rail_l10n_mx_payroll_extras.structure_liquidation', raise_if_not_found=False)
            if structure:
                values['estructura_extra'] = structure.id
        return values

    def _get_version_for_date(self, employee, target_date):
        version = employee._get_version(target_date) if employee and target_date else self.env['hr.version']
        if not version and employee:
            version = self.env['hr.version'].search([
                ('employee_id', '=', employee.id),
                ('date_version', '<=', target_date),
            ], order='date_version desc, id desc', limit=1)
        return version

    @api.onchange('employee_id', 'fecha_liquidacion')
    def _onchange_employee_id(self):
        for wizard in self:
            if not wizard.employee_id:
                wizard.version_id = False
                continue
            target_date = wizard.fecha_liquidacion or fields.Date.context_today(wizard)
            version = wizard._get_version_for_date(wizard.employee_id, target_date)
            wizard.version_id = version
            if version and not wizard.estructura:
                wizard.estructura = version.structure_type_id.default_struct_id
            if not wizard.estructura_extra:
                wizard.estructura_extra = self.env.ref(
                    'rail_l10n_mx_payroll_extras.structure_liquidation',
                    raise_if_not_found=False,
                )
            last_payslip = self.env['hr.payslip'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('state', 'in', ('validated', 'paid')),
            ], order='date_to desc, id desc', limit=1)
            if last_payslip:
                wizard.fecha_inicio = last_payslip.date_to + timedelta(days=1)
            elif version:
                wizard.fecha_inicio = version.contract_date_start or version.date_version

    @api.onchange('version_id')
    def _onchange_version_id(self):
        if self.version_id and not self.estructura:
            self.estructura = self.version_id.structure_type_id.default_struct_id

    def _reopen_action(self):
        self.ensure_one()
        action = self.env.ref('rail_l10n_mx_payroll_extras.action_wizard_liquidacion').read()[0]
        action['res_id'] = self.id
        return action

    def _rule_parameter(self, code, target_date):
        return self.env['hr.rule.parameter']._get_parameter_from_code(
            code,
            target_date,
            raise_if_not_found=True,
        )

    def _get_absence_days(self, start_date, end_date):
        self.ensure_one()
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ('validated', 'paid')),
            ('date_to', '>=', start_date),
            ('date_from', '<=', end_date),
        ])
        lines = slips.worked_days_line_ids.filtered(lambda line: line.code in ('FI', 'FJS', 'FR'))
        return sum(lines.mapped('number_of_days'))

    def _get_pending_vacation_balance(self):
        self.ensure_one()
        version = self.version_id
        if not version:
            return 0.0
        if 'rail_vacation_available_days' in version._fields:
            return max(version.rail_vacation_available_days or 0.0, 0.0)
        return 0.0

    def calculo_liquidacion(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Seleccione primero al empleado.'))
        if not self.fecha_inicio or not self.fecha_liquidacion:
            raise UserError(_('Capture la fecha inicial del último periodo y la fecha de liquidación.'))
        if self.fecha_inicio > self.fecha_liquidacion:
            raise UserError(_('La fecha inicial del último periodo no puede ser posterior a la liquidación.'))

        version = self.version_id or self._get_version_for_date(self.employee_id, self.fecha_liquidacion)
        if not version:
            raise UserError(_(
                'No se encontró una versión laboral para %(employee)s en la fecha de liquidación.',
                employee=self.employee_id.display_name,
            ))
        self.version_id = version

        first_contract_date = (
            self.employee_id.sudo()._get_first_contract_date(no_gap=False)
            or version.contract_date_start
            or version.date_version
        )
        if not first_contract_date:
            raise UserError(_('No existe una fecha inicial de antigüedad para el empleado.'))

        seniority_delta = self.fecha_liquidacion - first_contract_date
        self.antiguedad_anos = max(seniority_delta.days / 365.0, 0.0)

        details = version._rail_get_sbc_calculation_details(
            reference_date=self.fecha_liquidacion,
            raise_if_not_found=True,
        )
        daily_wage = details['daily_wage']
        integrated_daily_wage = details['uncapped_sbc']
        self.sueldo_calculo_monto = daily_wage if self.sueldo_calculo == '01' else integrated_daily_wage

        if self.indemnizacion:
            self.dias_totales = self.antiguedad_anos * self.dias_x_ano + self.dias_base
            self.monto_indemnizacion = self.dias_totales * self.sueldo_calculo_monto
        else:
            self.dias_totales = 0.0
            self.monto_indemnizacion = 0.0

        if self.antiguedad:
            minimum_wage = float(self._rule_parameter('l10n_mx_daily_min_wage', self.fecha_liquidacion) or 0.0)
            uma = self._rule_parameter('l10n_mx_uma', self.fecha_liquidacion) or {}
            daily_uma = uma.get('daily', 0.0) if isinstance(uma, dict) else float(uma or 0.0)
            legacy_limit = 2.0 * minimum_wage
            self.tope_prima_monto = minimum_wage if self.tope_prima == '01' else daily_uma
            years = round(self.antiguedad_anos) if self.round_antiguedad else round(self.antiguedad_anos, 2)
            if self.sueldo_calculo_monto > legacy_limit:
                base_amount = self.tope_prima_monto * 2.0
            else:
                base_amount = self.sueldo_calculo_monto
            self.monto_prima_antiguedad = years * 12.0 * base_amount
        else:
            self.monto_prima_antiguedad = 0.0
            self.tope_prima_monto = 0.0

        self.dias_pendientes_pagar = float((self.fecha_liquidacion - self.fecha_inicio).days + 1)

        year_start = date(self.fecha_liquidacion.year, 1, 1)
        accrual_start = max(first_contract_date, year_start)
        accrued_calendar_days = (self.fecha_liquidacion - accrual_start).days + 1
        absence_days = self._get_absence_days(accrual_start, self.fecha_liquidacion)
        eligible_days = max(accrued_calendar_days - absence_days, 0.0)
        christmas_days = float(self._rule_parameter('l10n_mx_christmas_bonus', self.fecha_liquidacion) or 0.0)
        days_in_year = (date(self.fecha_liquidacion.year, 12, 31) - year_start).days + 1
        self.dias_aguinaldo = christmas_days * eligible_days / days_in_year

        years_completed = max(relativedelta(self.fecha_liquidacion, first_contract_date).years, 0)
        anniversary = first_contract_date + relativedelta(years=years_completed)
        if anniversary > self.fecha_liquidacion:
            anniversary -= relativedelta(years=1)
        next_seniority_year = max(years_completed + 1, 1)
        holiday_table = self._rule_parameter('l10n_mx_holiday_tables', self.fecha_liquidacion) or {}
        vacation_entitlement = holiday_table.get(next_seniority_year)
        if vacation_entitlement is None and holiday_table:
            valid_keys = [key for key in holiday_table if key <= next_seniority_year]
            vacation_entitlement = holiday_table[max(valid_keys)] if valid_keys else 0.0
        vacation_entitlement = float(vacation_entitlement or 0.0)
        days_since_anniversary = max((self.fecha_liquidacion - anniversary).days + 1, 0)
        prorated_vacation = vacation_entitlement * days_since_anniversary / days_in_year
        self.dias_vacaciones = prorated_vacation + self._get_pending_vacation_balance()
        self.prima_vac = version.l10n_mx_holiday_bonus_rate or 0.0
        self.dias_prima_vac = self.dias_vacaciones * self.prima_vac / 100.0
        self.state = 'calculated'
        return self._reopen_action()

    def _input_type(self, xmlid):
        input_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not input_type:
            raise UserError(_('No se encontró el tipo de entrada %s.') % xmlid)
        return input_type

    def _prepare_input(self, xmlid, name, amount):
        return Command.create({
            'name': name,
            'input_type_id': self._input_type(xmlid).id,
            'amount': amount,
        })

    def _work_entry_type_by_code(self, code):
        self.ensure_one()
        country = self.employee_id.company_id.country_id
        work_entry_type = self.env['hr.work.entry.type'].search([
            ('code', '=', code),
            ('country_id', '=', country.id),
        ], limit=1)
        if not work_entry_type:
            work_entry_type = self.env['hr.work.entry.type'].search([
                ('code', '=', code),
                ('country_id', '=', False),
            ], limit=1)
        if not work_entry_type:
            raise UserError(_(
                'No se encontró un tipo de entrada de trabajo con código %(code)s para %(country)s.',
                code=code,
                country=country.display_name,
            ))
        return work_entry_type

    def _replace_worked_day_line(self, slip, code, name, days, hours=0.0):
        self.ensure_one()
        existing = slip.worked_days_line_ids.filtered(lambda line: line.code == code)
        if existing:
            existing.unlink()
        if not days and not hours:
            return self.env['hr.payslip.worked_days']
        return self.env['hr.payslip.worked_days'].create({
            'payslip_id': slip.id,
            'work_entry_type_id': self._work_entry_type_by_code(code).id,
            'name': name,
            'number_of_days': days,
            'number_of_hours': hours,
        })

    def _apply_liquidation_worked_days(self, slip):
        """Replace the ordinary worked-days lines with the liquidation concepts used in v18.

        The legacy liquidation wizard explicitly passed AGUI, VAC and PVC as worked-day lines.
        Odoo 19 computes only the work entries that physically exist in the period, therefore
        these accrued settlement concepts must be added after the native lines are generated
        and before the salary rules are computed.
        """
        self.ensure_one()
        version = self.version_id

        # Keep native absences/other work entries, but reproduce the v18 adjustment of the
        # payable attendance days before replacing WORK100/SEPT.
        excluded_from_reduction = {'WORK100', 'DFES', 'DFES_3', 'SEPT'}
        reduction_days = sum(
            line.number_of_days
            for line in slip.worked_days_line_ids
            if line.code not in excluded_from_reduction
        )
        payable_days = max((self.dias_pendientes_pagar or 0.0) - reduction_days, 0.0)

        work100_days = payable_days
        seventh_day_days = 0.0
        if version.schedule_pay == 'weekly' and version.rail_seventh_day:
            if version.rail_english_week:
                work100_days = max(payable_days - 2.0, 0.0)
                seventh_day_days = work100_days / 5.0 if work100_days else 0.0
            else:
                work100_days = max(payable_days - 1.0, 0.0)
                seventh_day_days = work100_days / 6.0 if work100_days else 0.0

        self.dias_pendientes_pagar = work100_days
        hours_per_day = slip._get_worked_day_lines_hours_per_day() or 0.0
        self._replace_worked_day_line(
            slip,
            'WORK100',
            _('Días a pagar'),
            work100_days,
            work100_days * hours_per_day,
        )
        self._replace_worked_day_line(
            slip,
            'SEPT',
            _('Séptimo día'),
            seventh_day_days,
            0.0,
        )
        self._replace_worked_day_line(
            slip,
            'AGUI',
            _('Días aguinaldo'),
            self.dias_aguinaldo or 0.0,
            0.0,
        )
        self._replace_worked_day_line(
            slip,
            'VAC',
            _('Días vacaciones'),
            self.dias_vacaciones or 0.0,
            0.0,
        )
        self._replace_worked_day_line(
            slip,
            'PVC',
            _('Prima vacacional'),
            self.dias_prima_vac or 0.0,
            0.0,
        )

    def _create_payslip(self, structure, date_from, date_to, name, inputs=None, run=None, liquidation_worked_days=False):
        self.ensure_one()
        if not structure:
            raise UserError(_('Seleccione la estructura salarial requerida para generar la liquidación.'))
        version = self.version_id
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee_id.id,
            'version_id': version.id,
            'date_from': date_from,
            'date_to': date_to,
            'name': name,
            'struct_id': structure.id,
            'payslip_run_id': run.id if run else False,
            'rail_apply_installments': False,
            'input_line_ids': inputs or [],
        })
        if liquidation_worked_days:
            self._apply_liquidation_worked_days(slip)
        slip.compute_sheet()
        return slip

    def calculo_create(self):
        self.ensure_one()
        if self.state == 'draft':
            self.calculo_liquidacion()
        if not self.version_id:
            raise UserError(_('No existe versión laboral para generar los recibos.'))
        if not self.estructura:
            raise UserError(_('Seleccione la estructura ordinaria.'))

        run = self.payslip_run_id
        if not run:
            run = self.env['hr.payslip.run'].create({
                'name': _('Liquidación - %s') % self.employee_id.display_name,
                'date_start': self.fecha_inicio,
                'date_end': self.fecha_liquidacion,
                'structure_id': self.estructura.id,
                'company_id': self.employee_id.company_id.id,
                'schedule_pay': self.version_id.schedule_pay,
            })
            self.payslip_run_id = run

        generated = self.env['hr.payslip']
        ordinary = self._create_payslip(
            self.estructura,
            self.fecha_inicio,
            self.fecha_liquidacion,
            _('Liquidación ordinaria - %s') % self.employee_id.display_name,
            inputs=[self._prepare_input(
                'rail_l10n_mx_payroll_extras.input_type_liquidation_savings_fund',
                _('Fondo ahorro'),
                self.fondo_ahorro,
            )] if self.fondo_ahorro else [],
            run=run,
            liquidation_worked_days=True,
        )
        generated |= ordinary

        if self.tipo_de_baja == '02':
            if not self.estructura_extra:
                raise UserError(_(
                    'Para una baja debe seleccionar la estructura de indemnización/finiquito.'
                ))
            inputs = []
            if self.monto_prima_antiguedad:
                inputs.append(self._prepare_input(
                    'rail_l10n_mx_payroll_extras.input_type_liquidation_seniority_bonus',
                    _('Prima antigüedad'), self.monto_prima_antiguedad,
                ))
            if self.monto_indemnizacion:
                inputs.append(self._prepare_input(
                    'rail_l10n_mx_payroll_extras.input_type_liquidation_indemnity',
                    _('Indemnización'), self.monto_indemnizacion,
                ))
            if self.pago_separacion:
                inputs.append(self._prepare_input(
                    'rail_l10n_mx_payroll_extras.input_type_liquidation_separation',
                    _('Pago por separación'), self.pago_separacion,
                ))
            extraordinary = self._create_payslip(
                self.estructura_extra,
                self.fecha_liquidacion,
                self.fecha_liquidacion,
                _('Liquidación extraordinaria - %s') % self.employee_id.display_name,
                inputs=inputs,
                run=run,
            )
            generated |= extraordinary

        self.generated_payslip_ids = [Command.set(generated.ids)]
        self.state = 'created'
        if len(generated) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Recibo de liquidación'),
                'res_model': 'hr.payslip',
                'view_mode': 'form',
                'res_id': generated.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recibos de liquidación'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated.ids)],
        }
