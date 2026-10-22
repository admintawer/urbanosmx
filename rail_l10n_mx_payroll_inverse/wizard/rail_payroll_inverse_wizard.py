# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError


class RailPayrollInverseWizard(models.TransientModel):
    _name = 'rail.payroll.inverse.wizard'
    _description = 'Cálculo inverso de nómina MX'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    candidate_name = fields.Char(
        string='Nombre candidato',
        help='Nombre usado para simulaciones prospectivas cuando todavía no existe una ficha de empleado.',
    )
    version_id = fields.Many2one('hr.version', string='Versión laboral')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    date_from = fields.Date(string='Desde', required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    effective_date = fields.Date(string='Fecha efectiva nueva versión', required=True, default=fields.Date.today)
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura salarial a simular',
        required=True,
        help='Estructura real de Odoo que se utilizará para ejecutar todas las reglas de la simulación.',
    )
    country_id = fields.Many2one(related='company_id.country_id', readonly=True)
    simulation_line_ids = fields.One2many(
        'rail.payroll.inverse.simulation.line',
        'wizard_id',
        string='Detalle de reglas simuladas',
        readonly=True,
    )

    # Functional fields kept from the v18 user flow.  The calculation itself
    # is still performed with the native Odoo 19 payroll engine.
    ultima_nomina = fields.Boolean(string='Última nómina del mes', default=False)
    mes = fields.Selection([
        ('01', 'Enero / Periodo 1'),
        ('02', 'Febrero / Periodo 2'),
        ('03', 'Marzo / Periodo 3'),
        ('04', 'Abril / Periodo 4'),
        ('05', 'Mayo / Periodo 5'),
        ('06', 'Junio / Periodo 6'),
        ('07', 'Julio / Periodo 7'),
        ('08', 'Agosto / Periodo 8'),
        ('09', 'Septiembre / Periodo 9'),
        ('10', 'Octubre / Periodo 10'),
        ('11', 'Noviembre / Periodo 11'),
        ('12', 'Diciembre / Periodo 12'),
    ], string='Mes de la nómina')
    current_wage = fields.Monetary(
        string='Sueldo actual',
        currency_field='currency_id',
        compute='_compute_reference_values',
    )
    current_sbc = fields.Float(
        string='Sueldo base de cotización (IMSS)',
        compute='_compute_reference_values',
    )
    simulation_schedule_pay = fields.Selection(
        selection=lambda self: self.env['hr.payroll.structure.type']._get_selection_schedule_pay(),
        string='Periodicidad de nómina simulada',
        help='Se usa únicamente cuando el empleado/candidato todavía no tiene una hr.version.',
    )
    simulation_contract_start_date = fields.Date(
        string='Fecha estimada de ingreso',
        default=fields.Date.today,
        help='Fecha usada para calcular antigüedad y factor de integración cuando todavía no existe una hr.version.',
    )
    simulation_holiday_bonus_rate = fields.Float(
        string='Prima vacacional simulada (%)',
        help='Prima vacacional que se aplicará al perfil técnico temporal de simulación cuando no existe hr.version.',
    )
    payroll_schedule_pay = fields.Selection(
        selection=lambda self: self.env['hr.payroll.structure.type']._get_selection_schedule_pay(),
        string='Periodicidad de nómina',
        compute='_compute_reference_values',
        readonly=True,
    )
    has_payroll_version = fields.Boolean(
        string='Tiene versión laboral utilizable',
        compute='_compute_reference_values',
        readonly=True,
        help='Indica que existe una versión con fecha de inicio de contrato suficiente para ejecutar la nómina nativa.',
    )
    current_monthly_wage = fields.Monetary(
        string='Sueldo actual equivalente mensual',
        currency_field='currency_id',
        compute='_compute_reference_values',
    )

    target_net_amount = fields.Monetary(string='Neto deseado', required=True, currency_field='currency_id')
    target_schedule_pay = fields.Selection(
        selection=lambda self: self.env['hr.payroll.structure.type']._get_selection_schedule_pay(),
        string='Periodicidad del neto deseado',
        required=True,
        help=(
            'Indica a qué periodicidad corresponde el neto capturado. Por ejemplo, si captura '
            '35,000 como mensual para un empleado quincenal, el cálculo buscará el salario que '
            'produzca el equivalente a 17,500 por quincena usando la tabla de periodicidades de México.'
        ),
    )
    target_payroll_net_amount = fields.Monetary(
        string='Neto objetivo del periodo de nómina',
        currency_field='currency_id',
        compute='_compute_target_payroll_net_amount',
        readonly=True,
    )
    tolerance = fields.Monetary(string='Tolerancia', default=0.05, currency_field='currency_id')
    max_iterations = fields.Integer(string='Iteraciones máximas', default=40)
    lower_wage = fields.Monetary(string='Salario bruto mínimo', currency_field='currency_id')
    upper_wage = fields.Monetary(string='Salario bruto máximo', currency_field='currency_id')
    fixed_sbc = fields.Float(string='SBC a aplicar')
    use_fixed_sbc = fields.Boolean(string='Usar SBC capturado')

    calculated_wage = fields.Monetary(
        string='Sueldo calculado del periodo de nómina', readonly=True, currency_field='currency_id')
    calculated_monthly_wage = fields.Monetary(
        string='Sueldo calculado equivalente mensual', readonly=True, currency_field='currency_id')
    calculated_payroll_net = fields.Monetary(
        string='Neto simulado del periodo de nómina', readonly=True, currency_field='currency_id',
        help='NET real producido por la estructura salarial seleccionada y usado como objetivo del cálculo inverso.')
    calculated_net = fields.Monetary(
        string='Neto equivalente en periodicidad seleccionada', readonly=True, currency_field='currency_id')
    calculated_real_payroll_net = fields.Monetary(
        string='Neto real estimado del recibo', readonly=True, currency_field='currency_id',
        help='NET completo de Odoo 19 incluyendo INFONAVIT, FONACOT, pensiones, fondo de ahorro y otras deducciones configuradas.')
    calculated_real_net = fields.Monetary(
        string='Neto real equivalente en periodicidad seleccionada', readonly=True, currency_field='currency_id')
    calculated_basic = fields.Monetary(string='Sueldo/percepciones base', readonly=True, currency_field='currency_id')
    calculated_allowances = fields.Monetary(string='Otras percepciones', readonly=True, currency_field='currency_id')
    calculated_isr = fields.Monetary(string='ISR', readonly=True, currency_field='currency_id')
    calculated_imss = fields.Monetary(string='IMSS trabajador', readonly=True, currency_field='currency_id')
    calculated_other_deductions = fields.Monetary(
        string='Deducciones totales', readonly=True, currency_field='currency_id')
    calculation_breakdown = fields.Text(string='Desglose del recibo simulado', readonly=True)
    calculated_difference = fields.Monetary(string='Diferencia vs. neto deseado', readonly=True, currency_field='currency_id')
    calculated_daily_wage = fields.Float(string='Salario diario calculado', readonly=True)
    calculated_integrated_daily_wage = fields.Float(string='Salario diario integrado calculado', readonly=True)
    calculated_sbc = fields.Float(string='SBC calculado', readonly=True)
    result_version_id = fields.Many2one('hr.version', string='Nueva versión creada', readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('applied', 'Aplicado'),
    ], default='draft', string='Estado', readonly=True)
    simulation_log = fields.Text(string='Bitácora de simulación', readonly=True)

    @api.depends(
        'version_id', 'version_id.rail_fixed_sbc', 'version_id.schedule_pay',
        'version_id.contract_date_start', 'simulation_schedule_pay', 'date_to',
    )
    def _compute_reference_values(self):
        for wizard in self:
            wage = wizard.version_id._get_contract_wage() if wizard.version_id else 0.0
            payroll_schedule = (
                wizard.version_id.schedule_pay
                if wizard.version_id
                else wizard.simulation_schedule_pay
            )
            wizard.current_wage = wage
            wizard.current_sbc = wizard.version_id.rail_fixed_sbc if wizard.version_id else 0.0
            wizard.payroll_schedule_pay = payroll_schedule
            wizard.has_payroll_version = bool(
                wizard.version_id
                and wizard.version_id.contract_date_start
                and wizard.version_id.schedule_pay
            )
            wizard.current_monthly_wage = wizard._rail_convert_schedule_amount(
                wage,
                payroll_schedule,
                'monthly',
                raise_if_not_found=False,
            )

    @api.depends('target_net_amount', 'target_schedule_pay', 'payroll_schedule_pay', 'date_to')
    def _compute_target_payroll_net_amount(self):
        for wizard in self:
            wizard.target_payroll_net_amount = wizard._rail_convert_schedule_amount(
                wizard.target_net_amount,
                wizard.target_schedule_pay,
                wizard.payroll_schedule_pay,
                raise_if_not_found=False,
            )

    @api.onchange('ultima_nomina')
    def _onchange_ultima_nomina(self):
        for wizard in self:
            if wizard.ultima_nomina and not wizard.mes:
                reference_date = wizard.date_to or fields.Date.context_today(wizard)
                wizard.mes = reference_date.strftime('%m')
            elif not wizard.ultima_nomina:
                wizard.mes = False

    @api.onchange(
        'target_net_amount', 'target_schedule_pay', 'ultima_nomina', 'mes', 'struct_id',
        'simulation_schedule_pay', 'simulation_contract_start_date', 'simulation_holiday_bonus_rate',
        'candidate_name',
    )
    def _onchange_functional_inputs(self):
        for wizard in self:
            if wizard.state != 'draft':
                wizard.state = 'draft'
                wizard.calculated_wage = 0.0
                wizard.calculated_monthly_wage = 0.0
                wizard.calculated_payroll_net = 0.0
                wizard.calculated_net = 0.0
                wizard.calculated_real_payroll_net = 0.0
                wizard.calculated_real_net = 0.0
                wizard.calculated_basic = 0.0
                wizard.calculated_allowances = 0.0
                wizard.calculated_isr = 0.0
                wizard.calculated_imss = 0.0
                wizard.calculated_other_deductions = 0.0
                wizard.calculation_breakdown = False
                wizard.calculated_difference = 0.0
                wizard.calculated_daily_wage = 0.0
                wizard.calculated_integrated_daily_wage = 0.0
                wizard.calculated_sbc = 0.0
                wizard.result_version_id = False
                wizard.simulation_log = False
                wizard.simulation_line_ids = [Command.clear()]

    @api.model
    def default_get(self, fields_list):
        """Prefill the wizard when launched from an employee form action."""
        values = super().default_get(fields_list)
        employee = self.env['hr.employee']

        if self.env.context.get('active_model') == 'hr.employee':
            active_id = self.env.context.get('active_id')
            if not active_id:
                active_ids = self.env.context.get('active_ids') or []
                active_id = active_ids[0] if len(active_ids) == 1 else False
            if active_id:
                employee = self.env['hr.employee'].browse(active_id).exists()

        if not employee and values.get('employee_id'):
            employee = self.env['hr.employee'].browse(values['employee_id']).exists()

        if not employee:
            structure = self.env.ref(
                'l10n_mx_hr_payroll.l10n_mx_regular_pay', raise_if_not_found=False
            )
            if structure:
                values.setdefault('struct_id', structure.id)
                values.setdefault('simulation_schedule_pay', structure.type_id.default_schedule_pay)
                values.setdefault('target_schedule_pay', structure.type_id.default_schedule_pay)
            values.setdefault('simulation_contract_start_date', values.get('date_from') or fields.Date.context_today(self))
            return values

        reference_date = values.get('date_from') or fields.Date.context_today(self)
        version = employee._get_version(reference_date)
        if not version and 'version_id' in employee._fields:
            version = employee.version_id
        if not version:
            version = employee.version_ids.sorted(
                key=lambda rec: (rec.date_version or rec.contract_date_start or fields.Date.from_string('1900-01-01'), rec.id),
                reverse=True,
            )[:1]

        values['employee_id'] = employee.id
        values['candidate_name'] = employee.name
        values['company_id'] = (employee.company_id or self.env.company).id

        # An hr.employee always has a technical hr.version through _inherits, but
        # candidates / incomplete hires can legitimately have no contract_date_start.
        # Such a version is not usable by the Mexican integration-factor rules, so
        # we treat it as a prospective simulation profile instead of passing it to
        # hr.payslip as if the employment process were complete.
        usable_version = version if version and version.contract_date_start and version.schedule_pay else self.env['hr.version']
        reference_version = version

        if usable_version:
            values['version_id'] = usable_version.id
            if usable_version.company_id:
                values['company_id'] = usable_version.company_id.id
            structure = usable_version.structure_type_id.default_struct_id
            if structure:
                values['struct_id'] = structure.id
            wage = usable_version._get_contract_wage()
            values.setdefault('lower_wage', 0.0)
            values.setdefault('upper_wage', max(wage * 2.0, 1.0))
            if usable_version.rail_fixed_sbc:
                values['fixed_sbc'] = usable_version.rail_fixed_sbc
            values.setdefault('target_schedule_pay', usable_version.schedule_pay)
        else:
            structure = (
                reference_version.structure_type_id.default_struct_id
                if reference_version and reference_version.structure_type_id
                else self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay', raise_if_not_found=False)
            )
            if structure:
                values.setdefault('struct_id', structure.id)
            simulation_schedule = (
                reference_version.schedule_pay
                if reference_version and reference_version.schedule_pay
                else (structure.type_id.default_schedule_pay if structure else False)
            )
            if simulation_schedule:
                values.setdefault('simulation_schedule_pay', simulation_schedule)
                values.setdefault('target_schedule_pay', simulation_schedule)
            if reference_version and reference_version.l10n_mx_holiday_bonus_rate:
                values.setdefault('simulation_holiday_bonus_rate', reference_version.l10n_mx_holiday_bonus_rate)
            values.setdefault('simulation_contract_start_date', values.get('date_from') or fields.Date.context_today(self))
            values.setdefault('lower_wage', 0.0)
            values.setdefault('upper_wage', 1.0)

        if values.get('ultima_nomina') and not values.get('mes'):
            reference_date = values.get('date_to') or fields.Date.context_today(self)
            if isinstance(reference_date, str):
                reference_date = fields.Date.from_string(reference_date)
            values['mes'] = reference_date.strftime('%m')

        return values

    @api.onchange('employee_id', 'date_from')
    def _onchange_employee_id(self):
        for wizard in self:
            if not wizard.employee_id:
                wizard.version_id = False
                continue
            wizard.candidate_name = wizard.employee_id.name
            wizard.company_id = wizard.employee_id.company_id or self.env.company
            reference_version = wizard.employee_id._get_version(wizard.date_from) if wizard.date_from else wizard.employee_id.version_id
            usable_version = (
                reference_version
                if reference_version and reference_version.contract_date_start and reference_version.schedule_pay
                else self.env['hr.version']
            )
            wizard.version_id = usable_version
            if usable_version:
                wizard.struct_id = usable_version.structure_type_id.default_struct_id
                wage = usable_version._get_contract_wage()
                wizard.lower_wage = 0.0
                wizard.upper_wage = max(wage * 2.0, 1.0)
                wizard.simulation_schedule_pay = usable_version.schedule_pay
                wizard.simulation_contract_start_date = usable_version.contract_date_start
                wizard.simulation_holiday_bonus_rate = usable_version.l10n_mx_holiday_bonus_rate
                if not wizard.target_schedule_pay:
                    wizard.target_schedule_pay = usable_version.schedule_pay
            else:
                structure = (
                    reference_version.structure_type_id.default_struct_id
                    if reference_version and reference_version.structure_type_id
                    else wizard.struct_id or self.env.ref(
                        'l10n_mx_hr_payroll.l10n_mx_regular_pay', raise_if_not_found=False
                    )
                )
                wizard.struct_id = structure
                if reference_version and reference_version.schedule_pay:
                    wizard.simulation_schedule_pay = reference_version.schedule_pay
                elif structure and not wizard.simulation_schedule_pay:
                    wizard.simulation_schedule_pay = structure.type_id.default_schedule_pay
                if reference_version and reference_version.l10n_mx_holiday_bonus_rate:
                    wizard.simulation_holiday_bonus_rate = reference_version.l10n_mx_holiday_bonus_rate
                if not wizard.simulation_contract_start_date:
                    wizard.simulation_contract_start_date = wizard.date_from or fields.Date.context_today(wizard)
                if not wizard.target_schedule_pay:
                    wizard.target_schedule_pay = wizard.simulation_schedule_pay
                wizard.lower_wage = 0.0
                wizard.upper_wage = max(float(wizard.target_net_amount or 0.0) * 2.0, 1.0)

    @api.onchange('version_id')
    def _onchange_version_id(self):
        for wizard in self:
            if wizard.version_id:
                wizard.employee_id = wizard.version_id.employee_id
                wizard.candidate_name = wizard.employee_id.name
                wizard.company_id = wizard.version_id.company_id or wizard.employee_id.company_id or self.env.company
                wizard.struct_id = wizard.version_id.structure_type_id.default_struct_id
                wizard.simulation_schedule_pay = wizard.version_id.schedule_pay
                wizard.simulation_contract_start_date = wizard.version_id.contract_date_start or wizard.version_id.date_version
                wizard.simulation_holiday_bonus_rate = wizard.version_id.l10n_mx_holiday_bonus_rate
                wage = wizard.version_id._get_contract_wage()
                wizard.lower_wage = wizard.lower_wage or 0.0
                wizard.upper_wage = wizard.upper_wage or max(wage * 2.0, 1.0)
                if not wizard.fixed_sbc:
                    wizard.fixed_sbc = wizard.version_id.rail_fixed_sbc
                if not wizard.target_schedule_pay:
                    wizard.target_schedule_pay = wizard.version_id.schedule_pay

    @api.model_create_multi
    def create(self, vals_list):
        # Programmatic callers (notably the batch import wizard) do not execute
        # default_get. Fill the target periodicity from the selected version so
        # existing integrations preserve the old 'amount per payroll period' behavior.
        for vals in vals_list:
            if vals.get('version_id'):
                version = self.env['hr.version'].browse(vals['version_id']).exists()
                if version:
                    if not vals.get('target_schedule_pay'):
                        vals['target_schedule_pay'] = version.schedule_pay
                    if not vals.get('struct_id') and version.structure_type_id.default_struct_id:
                        vals['struct_id'] = version.structure_type_id.default_struct_id.id
            elif vals.get('struct_id'):
                structure = self.env['hr.payroll.structure'].browse(vals['struct_id']).exists()
                if structure:
                    vals.setdefault('simulation_schedule_pay', structure.type_id.default_schedule_pay)
                    vals.setdefault('target_schedule_pay', structure.type_id.default_schedule_pay)
            vals.setdefault('simulation_contract_start_date', vals.get('date_from') or fields.Date.context_today(self))
        return super().create(vals_list)

    def _rail_get_schedule_days(self, schedule_pay, raise_if_not_found=True):
        self.ensure_one()
        if not schedule_pay:
            if raise_if_not_found:
                raise UserError(_('No fue posible determinar la periodicidad para el cálculo inverso.'))
            return 0.0
        reference_date = self.date_to or self.effective_date or fields.Date.context_today(self)
        schedule_table = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_mx_schedule_table', reference_date, raise_if_not_found=raise_if_not_found
        ) or {}
        days = schedule_table.get(schedule_pay) if isinstance(schedule_table, dict) else False
        if not days and raise_if_not_found:
            raise UserError(_(
                'No existe configuración de días para la periodicidad %(schedule)s en '
                'l10n_mx_schedule_table.'
            ) % {'schedule': schedule_pay})
        return float(days or 0.0)

    def _rail_convert_schedule_amount(
        self, amount, source_schedule, target_schedule, raise_if_not_found=True
    ):
        """Normalize an amount between Mexican payroll schedules.

        Odoo 19 MX defines each schedule using l10n_mx_schedule_table
        (weekly=7, bi-weekly=15, monthly=30, ...). This conversion makes the
        meaning of the desired net explicit without replacing the native tax
        calculation: the payslip is still simulated with the employee's real
        schedule; only the target/result amount is normalized for comparison.
        """
        self.ensure_one()
        if not amount or not source_schedule or not target_schedule:
            return 0.0
        source_days = self._rail_get_schedule_days(source_schedule, raise_if_not_found)
        target_days = self._rail_get_schedule_days(target_schedule, raise_if_not_found)
        if not source_days or not target_days:
            return 0.0
        return float(amount) * target_days / source_days

    def _rail_get_target_payroll_net(self):
        self.ensure_one()
        return self._rail_convert_schedule_amount(
            self.target_net_amount,
            self.target_schedule_pay,
            self.payroll_schedule_pay,
            raise_if_not_found=True,
        )

    def _rail_get_processed_payslips(self):
        self.ensure_one()
        return self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('structure_code', '=', 'MX_REGULAR'),
            ('state', 'in', ['validated', 'paid']),
        ], order='date_to desc, id desc')

    def _rail_prepare_last_payroll_period(self):
        """Resolve the final payroll period from real processed payslips.

        v18 used a configured monthly table only to accumulate the payrolls of
        the selected month.  Odoo 19 accumulates Mexican subsidy from actual
        validated/paid payslips.  For that reason we determine the next period
        from the employee's real payroll history instead of inventing calendar
        boundaries.
        """
        self.ensure_one()
        if not self.ultima_nomina:
            return
        if not self.mes:
            raise UserError(_('Seleccione el mes de la nómina.'))
        if not self.version_id:
            raise UserError(_('El empleado no tiene una versión laboral vigente.'))

        month_number = int(self.mes)
        processed = self._rail_get_processed_payslips()
        month_slips = processed.filtered(
            lambda slip: slip.date_from and slip.date_to
            and (slip.date_from.month == month_number or slip.date_to.month == month_number)
        )
        if not month_slips:
            raise UserError(_(
                'No existen nóminas validadas o pagadas del mes seleccionado para %(employee)s. '
                'No es posible determinar de forma segura cuál es la última nómina del mes.'
            ) % {'employee': self.employee_id.display_name})

        latest = month_slips.sorted(key=lambda slip: (slip.date_to, slip.id), reverse=True)[:1]
        next_date_from = latest.date_to + timedelta(days=1)
        if next_date_from.month != month_number:
            raise UserError(_(
                'La nómina %(payslip)s ya cubre el último periodo procesado del mes seleccionado. '
                'No existe un periodo posterior dentro de ese mes para calcular.'
            ) % {'payslip': latest.display_name})

        schedule = self.version_id.schedule_pay
        if not schedule:
            raise UserError(_('La versión laboral no tiene periodicidad de pago configurada.'))
        delta = self.env['hr.payslip']._schedule_timedelta(schedule, next_date_from, 'MX')
        next_date_to = next_date_from + delta

        following_date_from = next_date_to + timedelta(days=1)
        if following_date_from.month == month_number:
            raise UserError(_(
                'Aún existen periodos anteriores a la última nómina del mes %(month)s sin procesar. '
                'Valide o pague esos periodos primero para que el cálculo mensual use acumulados reales.'
            ) % {'month': dict(self._fields['mes'].selection).get(self.mes, self.mes)})

        self.date_from = next_date_from
        self.date_to = next_date_to
        version = self.employee_id._get_version(next_date_from)
        if version:
            self.version_id = version
            self.company_id = version.company_id or self.employee_id.company_id or self.env.company
            if not self.struct_id:
                self.struct_id = version.structure_type_id.default_struct_id
            wage = version._get_contract_wage()
            self.lower_wage = 0.0
            self.upper_wage = max(wage * 2.0, 1.0)

    def _rail_get_default_structure(self):
        self.ensure_one()
        structure = self.struct_id or (self.version_id.structure_type_id.default_struct_id if self.version_id else False)
        if not structure:
            raise UserError(_('Seleccione la estructura salarial que desea simular.'))
        if structure.country_id and self.company_id.country_id and structure.country_id != self.company_id.country_id:
            raise UserError(_(
                'La estructura salarial %(structure)s pertenece a %(structure_country)s y no puede '
                'simularse para una compañía de %(company_country)s.'
            ) % {
                'structure': structure.display_name,
                'structure_country': structure.country_id.display_name,
                'company_country': self.company_id.country_id.display_name,
            })
        if not structure.rule_ids:
            raise UserError(_('La estructura salarial %s no tiene reglas configuradas.') % structure.display_name)
        if not structure.rule_ids.filtered(lambda rule: rule.code == 'NET'):
            raise UserError(_(
                'La estructura salarial %s no contiene una regla con código NET. '
                'El cálculo inverso necesita el NET nativo para encontrar el sueldo objetivo.'
            ) % structure.display_name)
        return structure

    def _rail_get_simulation_profile_values(self):
        self.ensure_one()
        structure = self._rail_get_default_structure()
        usable_version = (
            self.version_id
            if self.version_id and self.version_id.contract_date_start and self.version_id.schedule_pay
            else self.env['hr.version']
        )
        schedule_pay = usable_version.schedule_pay if usable_version else self.simulation_schedule_pay
        if not schedule_pay:
            raise UserError(_('Seleccione la periodicidad de nómina que desea simular.'))
        contract_start = usable_version.contract_date_start if usable_version else self.simulation_contract_start_date
        if not contract_start:
            raise UserError(_('Indique la fecha estimada de ingreso para la simulación del candidato.'))
        if not usable_version and self.simulation_holiday_bonus_rate <= 0:
            raise UserError(_(
                'Indique la prima vacacional (%) aplicable al candidato para calcular correctamente '
                'el factor de integración.'
            ))
        if not usable_version and self.simulation_holiday_bonus_rate > 100:
            raise UserError(_('La prima vacacional simulada no puede ser mayor a 100%.'))
        return {
            'company_id': self.company_id.id,
            'date_version': contract_start,
            'contract_date_start': contract_start,
            'structure_type_id': structure.type_id.id,
            'schedule_pay': schedule_pay,
            'wage': 0.0,
            'l10n_mx_holiday_bonus_rate': (
                usable_version.l10n_mx_holiday_bonus_rate
                if usable_version
                else self.simulation_holiday_bonus_rate
            ),
            'resource_calendar_id': self.company_id.resource_calendar_id.id,
        }

    def _rail_prepare_simulation_profile(self):
        """Return employee/version records that can be used by native payroll.

        Odoo 19 salary rules require a real ``hr.version`` record. A candidate
        may legitimately have no version yet, so the calculator creates a
        technical temporary version (or a temporary employee+version for batch
        candidate-only simulations), computes the payslips, copies the result
        to transient lines and then removes the technical records.
        """
        self.ensure_one()
        usable_version = (
            self.version_id
            if self.version_id and self.version_id.contract_date_start and self.version_id.schedule_pay
            else self.env['hr.version']
        )
        if usable_version:
            return self.employee_id, usable_version, False, False

        context = dict(
            self.env.context,
            salary_simulation=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            rail_skip_imss_auto_incidence=True,
            rail_skip_sbc_autocalculate=True,
        )
        profile_values = self._rail_get_simulation_profile_values()

        if not self.candidate_name and not self.employee_id:
            raise UserError(_('Seleccione un empleado o indique el nombre del candidato.'))

        # Do not attach a temporary version to a real employee. Besides avoiding
        # transient changes in their version history/current_version_id, this also
        # avoids collisions with the technical _inherits version that Odoo creates
        # when the employee record exists but hiring is still incomplete.
        employee_values = {
            'name': self.candidate_name or self.employee_id.name,
            'company_id': self.company_id.id,
            **profile_values,
        }
        employee = self.env['hr.employee'].with_context(context).create(employee_values)
        version = employee._get_version(self.date_from or fields.Date.context_today(self))
        if not version:
            version = employee.version_ids[:1]
        if not version:
            work_contact = employee.work_contact_id
            employee.unlink()
            if work_contact.exists() and not work_contact.employee_ids:
                work_contact.sudo().unlink()
            raise UserError(_('No fue posible construir el perfil técnico temporal del candidato.'))
        return employee, version, False, employee

    def _rail_cleanup_simulation_profile(self, temporary_version=False, temporary_employee=False):
        context = dict(
            self.env.context,
            salary_simulation=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            rail_skip_imss_auto_incidence=True,
            rail_skip_sbc_autocalculate=True,
        )
        if temporary_version and temporary_version.exists():
            temporary_version.with_context(context).unlink()
        if temporary_employee and temporary_employee.exists():
            work_contact = temporary_employee.work_contact_id
            temporary_employee.with_context(context).unlink()
            if work_contact.exists() and not work_contact.employee_ids and not work_contact.user_ids:
                work_contact.sudo().unlink()

    def _rail_category_has_code(self, category, code):
        """Return whether ``category`` is or descends from the requested code."""
        current = category
        while current:
            if current.code == code:
                return True
            current = current.parent_id
        return False

    def _rail_get_simulation_metrics(self, payslip):
        """Capture the real result of the selected salary structure.

        The inverse search must converge against the native ``NET`` produced by
        the selected structure.  We also copy every computed payslip line to
        transient values before the temporary payslip is deleted, so the user
        can audit the simulation with the same columns shown on a payslip.
        """
        self.ensure_one()
        payslip.invalidate_recordset(['line_ids', 'net_wage'])
        lines = payslip.line_ids.sorted(key=lambda line: (line.sequence, line.id))

        basic = 0.0
        allowances = 0.0
        deductions = 0.0
        isr = 0.0
        imss = 0.0
        line_values = []
        isr_codes = {'ISR', 'ISR_ADJUSTMENT', 'ISR_HOLIDAY_TAX'}

        for line in lines:
            total = float(line.total or 0.0)
            category = line.category_id
            is_basic = self._rail_category_has_code(category, 'BASIC')
            is_allowance = self._rail_category_has_code(category, 'ALW')
            is_deduction = self._rail_category_has_code(category, 'DED')
            is_imss = self._rail_category_has_code(category, 'IMSS_EMPLOYEE')
            is_net = line.code == 'NET' or self._rail_category_has_code(category, 'NET')
            is_isr = line.code in isr_codes

            if is_basic:
                basic += total
            if is_allowance:
                allowances += total
            if is_deduction:
                deductions += total
            if is_isr:
                isr += total
            if is_imss:
                imss += total

            if is_net:
                line_type = 'net'
            elif is_deduction or total < 0:
                line_type = 'deduction'
            elif is_basic or is_allowance or total > 0:
                line_type = 'perception'
            else:
                line_type = 'other'

            line_values.append({
                'sequence': line.sequence,
                'salary_rule_id': line.salary_rule_id.id,
                'name': line.name or line.salary_rule_id.name or '',
                'code': line.code or '',
                'category_id': category.id,
                'quantity': line.quantity,
                'rate': line.rate,
                'amount': line.amount,
                'total': line.total,
                'ytd': line.ytd,
                'appears_on_payslip': line.appears_on_payslip,
                'line_type': line_type,
            })

        net_line = lines.filtered(lambda line: line.code == 'NET')[:1]
        real_net = float(
            payslip.net_wage
            if payslip.net_wage is not None
            else (net_line.total if net_line else 0.0)
        )
        return {
            'real_net': real_net,
            'basic': basic,
            'allowances': allowances,
            'isr': abs(isr),
            'imss': abs(imss),
            'deductions': abs(deductions),
            'line_values': line_values,
        }

    def _rail_create_simulation_payslip(self, candidate_wage, employee, version):
        self.ensure_one()
        if not version:
            raise UserError(_('No fue posible construir una versión técnica para simular.'))
        if not self.date_from or not self.date_to:
            raise UserError(_('El periodo de simulación es obligatorio.'))
        if self.date_from > self.date_to:
            raise UserError(_('La fecha inicial no puede ser mayor que la fecha final.'))
        structure = self._rail_get_default_structure()
        simulation_start_date = (
            version.contract_date_start
            if self.version_id and version == self.version_id
            else (self.simulation_contract_start_date or version.contract_date_start)
        )
        simulation_bonus_rate = (
            version.l10n_mx_holiday_bonus_rate
            if self.version_id and version == self.version_id
            else self.simulation_holiday_bonus_rate
        )
        context = dict(
            self.env.context,
            salary_simulation=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            rail_inverse_candidate_wage=float(candidate_wage or 0.0),
            rail_inverse_version_id=version.id,
            rail_inverse_contract_start_date=(
                fields.Date.to_string(simulation_start_date) if simulation_start_date else False
            ),
            rail_inverse_holiday_bonus_rate=float(simulation_bonus_rate or 0.0),
        )
        Payslip = self.env['hr.payslip'].with_context(context)
        payslip = Payslip.create({
            'name': _('Simulación cálculo inverso - %s') % (employee.display_name or self.candidate_name),
            'employee_id': employee.id,
            'version_id': version.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'struct_id': structure.id,
            'company_id': self.company_id.id,
            'note': _('Recibo temporal generado por cálculo inverso. Debe eliminarse automáticamente.'),
        })
        return payslip.with_context(context)

    def _rail_simulate_net(self, candidate_wage, employee, version, return_metrics=False):
        self.ensure_one()
        payslip = self._rail_create_simulation_payslip(candidate_wage, employee, version)
        try:
            payslip.compute_sheet()
            metrics = self._rail_get_simulation_metrics(payslip)
            return metrics if return_metrics else metrics['real_net']
        finally:
            if payslip.exists() and payslip.state in ('draft', 'cancel'):
                payslip.unlink()

    def _rail_expand_upper_bound(self, lower, upper, log_lines, employee, version):
        self.ensure_one()
        target = self._rail_get_target_payroll_net()
        upper = max(float(upper or 0.0), 1.0)
        for index in range(20):
            net = self._rail_simulate_net(upper, employee, version)
            log_lines.append(_('Expansión %(i)s: salario=%(w).6f NET=%(n).6f') % {
                'i': index + 1,
                'w': upper,
                'n': net,
            })
            if net >= target:
                return lower, upper, net
            lower = upper
            upper *= 2.0
        raise UserError(_('No fue posible encontrar un salario bruto superior que alcance el neto objetivo. Revise reglas salariales y descuentos.'))

    def _rail_reopen_wizard_action(self):
        """Reopen this exact TransientModel record in the modal.

        Returning a bare ``True`` from a wizard object button makes the web
        client finish the dialog flow. The calculation results are written on
        this transient record, so we explicitly reopen the same ``res_id`` to
        keep the user in the wizard and display them immediately.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cálculo inverso'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_calculate(self):
        self.ensure_one()
        self._action_calculate_one()
        return self._rail_reopen_wizard_action()

    def _action_calculate_one(self):
        self.ensure_one()
        if self.ultima_nomina:
            self._rail_prepare_last_payroll_period()
        if self.target_net_amount <= 0:
            raise UserError(_('El neto objetivo debe ser mayor a cero.'))
        if not self.target_schedule_pay:
            raise UserError(_('Seleccione la periodicidad del neto deseado.'))
        if self.max_iterations <= 0:
            raise UserError(_('Las iteraciones máximas deben ser mayores a cero.'))
        if self.tolerance < 0:
            raise UserError(_('La tolerancia no puede ser negativa.'))
        if not self.employee_id and not self.candidate_name:
            raise UserError(_('Seleccione un empleado o indique el nombre del candidato.'))
        if self.version_id and self.employee_id and self.version_id.employee_id != self.employee_id:
            raise UserError(_('La versión laboral seleccionada no pertenece al empleado.'))

        self._rail_get_default_structure()
        employee = version = temporary_version = temporary_employee = False
        try:
            employee, version, temporary_version, temporary_employee = self._rail_prepare_simulation_profile()
            payroll_schedule = version.schedule_pay
            payroll_target = self._rail_convert_schedule_amount(
                self.target_net_amount,
                self.target_schedule_pay,
                payroll_schedule,
                raise_if_not_found=True,
            )
            if payroll_target <= 0:
                raise UserError(_('No fue posible convertir el neto deseado a la periodicidad de la nómina.'))

            lower = float(self.lower_wage or 0.0)
            upper = float(self.upper_wage or 0.0)
            reference_wage = version._get_contract_wage() if self.version_id else 0.0
            if upper <= lower:
                upper = max(reference_wage * 2.0, payroll_target * 2.0, lower + 1.0)
            log_lines = []
            lower, upper, upper_net = self._rail_expand_upper_bound(
                lower, upper, log_lines, employee, version
            )

            best_wage = upper
            best_net = upper_net
            tolerance = self.currency_id.round(self.tolerance) if self.currency_id else self.tolerance
            for index in range(self.max_iterations):
                candidate = (lower + upper) / 2.0
                net = self._rail_simulate_net(candidate, employee, version)
                diff = net - payroll_target
                log_lines.append(_('Iteración %(i)s: salario=%(w).6f NET=%(n).6f diferencia=%(d).6f') % {
                    'i': index + 1,
                    'w': candidate,
                    'n': net,
                    'd': diff,
                })
                if abs(diff) <= tolerance:
                    best_wage = candidate
                    best_net = net
                    break
                if net < payroll_target:
                    lower = candidate
                else:
                    upper = candidate
                    best_wage = candidate
                    best_net = net
            else:
                best_net = self._rail_simulate_net(best_wage, employee, version)

            final_metrics = self._rail_simulate_net(
                best_wage, employee, version, return_metrics=True
            )
            best_net = final_metrics['real_net']

            sbc_details = version._rail_get_sbc_calculation_details(
                reference_date=self.effective_date,
                wage=best_wage,
                raise_if_not_found=True,
            )
            calculated_sbc = self.fixed_sbc if self.use_fixed_sbc else sbc_details['sbc']
            equivalent_net = self._rail_convert_schedule_amount(
                best_net,
                payroll_schedule,
                self.target_schedule_pay,
                raise_if_not_found=True,
            )
            monthly_wage = self._rail_convert_schedule_amount(
                best_wage,
                payroll_schedule,
                'monthly',
                raise_if_not_found=True,
            )
            log_lines.append(_(
                'Objetivo capturado=%(target).6f (%(target_schedule)s); objetivo del periodo de nómina='
                '%(payroll_target).6f (%(payroll_schedule)s); NET simulado=%(period_net).6f; '
                'NET equivalente=%(equivalent_net).6f.'
            ) % {
                'target': self.target_net_amount,
                'target_schedule': self.target_schedule_pay,
                'payroll_target': payroll_target,
                'payroll_schedule': payroll_schedule,
                'period_net': best_net,
                'equivalent_net': equivalent_net,
            })
            self.write({
                'calculated_wage': best_wage,
                'calculated_monthly_wage': monthly_wage,
                'calculated_payroll_net': best_net,
                'calculated_net': equivalent_net,
                'calculated_real_payroll_net': final_metrics['real_net'],
                'calculated_real_net': equivalent_net,
                'calculated_basic': final_metrics['basic'],
                'calculated_allowances': final_metrics['allowances'],
                'calculated_isr': final_metrics['isr'],
                'calculated_imss': final_metrics['imss'],
                'calculated_other_deductions': final_metrics['deductions'],
                'calculation_breakdown': False,
                'simulation_line_ids': [Command.clear()] + [
                    Command.create(values) for values in final_metrics['line_values']
                ],
                'calculated_difference': equivalent_net - self.target_net_amount,
                'calculated_daily_wage': sbc_details['daily_wage'],
                'calculated_integrated_daily_wage': (
                    sbc_details['daily_wage'] * sbc_details['integration_factor']
                ),
                'calculated_sbc': calculated_sbc,
                'state': 'calculated',
                'simulation_log': '\n'.join(log_lines),
            })
        finally:
            self._rail_cleanup_simulation_profile(temporary_version, temporary_employee)
        return True

    def _rail_prepare_new_version_values(self):
        self.ensure_one()
        if not self.calculated_wage:
            raise UserError(_('Calcule el salario antes de crear la nueva versión.'))
        wage_field = self.version_id._get_contract_wage_field() if self.version_id else 'wage'
        vals = {wage_field: self.calculated_wage}
        if self.use_fixed_sbc:
            vals['rail_fixed_sbc'] = self.fixed_sbc
        return vals

    def action_apply_new_version(self):
        self.ensure_one()
        self._action_apply_new_version_one()
        return self._rail_reopen_wizard_action()

    def _action_apply_new_version_one(self):
        self.ensure_one()
        if self.state != 'calculated':
            raise UserError(_('Primero debe calcular el salario inverso.'))
        if not self.employee_id:
            raise UserError(_(
                'Esta es una simulación de candidato sin ficha de empleado. El resultado puede consultarse, '
                'pero no es posible crear una hr.version hasta que exista el empleado.'
            ))
        if not self.effective_date:
            raise UserError(_('La fecha efectiva es obligatoria.'))
        existing_same_date = self.employee_id.version_ids.filtered(lambda version: version.date_version == self.effective_date)
        if existing_same_date:
            raise UserError(_(
                'Ya existe una versión laboral para %(employee)s con fecha %(date)s. '
                'Cambie la fecha efectiva o actualice esa versión manualmente.'
            ) % {'employee': self.employee_id.display_name, 'date': self.effective_date})
        if self.version_id:
            new_version = self.version_id.rail_create_new_version(
                effective_date=self.effective_date,
                values=self._rail_prepare_new_version_values(),
            )
        else:
            structure = self._rail_get_default_structure()
            vals = {
                'employee_id': self.employee_id.id,
                'company_id': self.company_id.id,
                'date_version': self.effective_date,
                'contract_date_start': self.simulation_contract_start_date or self.effective_date,
                'structure_type_id': structure.type_id.id,
                'schedule_pay': self.simulation_schedule_pay,
                'l10n_mx_holiday_bonus_rate': self.simulation_holiday_bonus_rate,
                'resource_calendar_id': self.company_id.resource_calendar_id.id,
                **self._rail_prepare_new_version_values(),
            }
            if not self.use_fixed_sbc:
                vals['rail_fixed_sbc'] = self.calculated_sbc
            new_version = self.env['hr.version'].create(vals)
            self.version_id = new_version
        self.write({
            'result_version_id': new_version.id,
            'state': 'applied',
        })
        return True

    def action_open_new_version(self):
        self.ensure_one()
        if not self.result_version_id:
            raise UserError(_('Aún no se ha creado una nueva versión.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nueva versión laboral'),
            'res_model': 'hr.version',
            'view_mode': 'form',
            'res_id': self.result_version_id.id,
            'target': 'current',
        }


class RailPayrollInverseSimulationLine(models.TransientModel):
    _name = 'rail.payroll.inverse.simulation.line'
    _description = 'Detalle de regla simulada cálculo inverso MX'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'rail.payroll.inverse.wizard', required=True, ondelete='cascade', index=True
    )
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
    sequence = fields.Integer(string='Secuencia', readonly=True)
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Regla salarial', readonly=True)
    name = fields.Char(string='Nombre', readonly=True)
    code = fields.Char(string='Código', readonly=True)
    category_id = fields.Many2one('hr.salary.rule.category', string='Categoría', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True, digits='Payroll')
    rate = fields.Float(string='Tasa (%)', readonly=True, digits='Payroll Rate')
    amount = fields.Monetary(string='Importe', readonly=True, currency_field='currency_id')
    total = fields.Monetary(string='Total', readonly=True, currency_field='currency_id')
    ytd = fields.Monetary(string='Acumulado', readonly=True, currency_field='currency_id')
    appears_on_payslip = fields.Boolean(string='Mostrar en recibo', readonly=True)
    line_type = fields.Selection([
        ('perception', 'Percepción'),
        ('deduction', 'Deducción'),
        ('net', 'Neto'),
        ('other', 'Otra'),
    ], string='Tipo', readonly=True)
