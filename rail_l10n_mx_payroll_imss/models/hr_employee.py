# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    rail_imss_incidence_ids = fields.One2many('rail.imss.incidence', 'employee_id', string='Incidencias IMSS')
    rail_imss_incidence_count = fields.Integer(
        string='Incidencias IMSS',
        compute='_compute_rail_imss_incidence_count',
    )

    # Datos permanentes del trabajador usados por SUA / IDSE. Se mantienen los
    # nombres técnicos de la versión 19.0.1.0.6 para no romper integraciones ni
    # importaciones existentes, pero la fuente física pasa a hr.employee.
    rail_imss_clinic = fields.Char(
        string='Unidad de medicina familiar',
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
        help='Unidad de medicina familiar requerida por layouts SUA/IDSE.',
    )
    rail_imss_subdelegation_code = fields.Char(
        string='Clave subdelegación',
        size=2,
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
        help='Clave de subdelegación de 2 dígitos usada por IDSE/SUA.',
    )
    rail_imss_worker_type = fields.Selection([
        ('1', '1 - Trabajador permanente'),
        ('2', '2 - Trabajador eventual en ciudad'),
        ('3', '3 - Trabajador eventual en construcción'),
        ('4', '4 - Eventual de campo'),
    ], string='Tipo de trabajador SUA', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_imss_salary_type = fields.Selection([
        ('0', '0 - Salario fijo'),
        ('1', '1 - Salario variable'),
        ('2', '2 - Salario mixto'),
    ], string='Tipo de salario SUA', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_imss_workday_type = fields.Selection([
        ('1', '1 - Un día'),
        ('2', '2 - Dos días'),
        ('3', '3 - Tres días'),
        ('4', '4 - Cuatro días'),
        ('5', '5 - Cinco días'),
        ('6', '6 - Jornada reducida'),
        ('0', '0 - Jornada normal'),
    ], string='Tipo de jornada SUA', groups='hr_payroll.group_hr_payroll_user', tracking=True)
    rail_sbc_effective_date = fields.Date(
        related='version_id.rail_sbc_effective_date',
        readonly=False,
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    rail_previous_sbc = fields.Float(
        related='version_id.rail_previous_sbc',
        readonly=False,
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )

    def write(self, vals):
        watched_fields = {
            'rail_imss_clinic',
            'rail_imss_subdelegation_code',
            'rail_imss_worker_type',
            'rail_imss_salary_type',
            'rail_imss_workday_type',
            'private_zip',
            'ssnid',
        }
        result = super().write(vals)
        if (
            watched_fields.intersection(vals)
            and not self.env.context.get('rail_skip_imss_employee_refresh')
        ):
            self.mapped('rail_imss_incidence_ids').filtered(
                lambda event: event.automatic and event.state != 'cancel'
            )._rail_refresh_automatic_state()
        return result

    @api.model
    def _rail_migrate_imss_fields_from_versions(self):
        """Copia datos legacy desde columnas físicas antiguas de hr.version.

        En 19.0.1.0.6 estos campos eran físicos en ``hr.version``. Al actualizar,
        Odoo conserva las columnas PostgreSQL aunque el ORM las convierta en
        related. Esta rutina idempotente toma primero la versión vigente/más
        reciente, llena únicamente campos vacíos del empleado y nunca sobrescribe
        información capturada directamente en ``hr.employee``.
        """
        version_table = self.env['hr.version']._table
        legacy_fields = [
            'rail_imss_clinic',
            'rail_imss_subdelegation_code',
            'rail_imss_worker_type',
            'rail_imss_salary_type',
            'rail_imss_workday_type',
        ]
        self.env.cr.execute(
            """
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name = %s
                   AND column_name = ANY(%s)
            """,
            [version_table, legacy_fields],
        )
        available = {row[0] for row in self.env.cr.fetchall()}
        available_fields = [name for name in legacy_fields if name in available]
        if not available_fields:
            return True

        quoted_columns = ', '.join('"%s"' % name for name in available_fields)
        self.env.cr.execute(
            f"""
                SELECT employee_id, date_version, id, {quoted_columns}
                  FROM {version_table}
                 WHERE employee_id IS NOT NULL
                 ORDER BY employee_id,
                          CASE WHEN date_version IS NOT NULL
                                    AND date_version <= CURRENT_DATE THEN 0 ELSE 1 END,
                          date_version DESC NULLS LAST,
                          id DESC
            """
        )

        values_by_employee = {}
        for row in self.env.cr.fetchall():
            employee_id = row[0]
            candidate = values_by_employee.setdefault(employee_id, {})
            for field_name, value in zip(available_fields, row[3:]):
                if field_name not in candidate and value not in (None, False, ''):
                    candidate[field_name] = value

        employees = self.with_context(active_test=False).browse(list(values_by_employee))
        touched = self.browse()
        for employee in employees.exists():
            incoming = values_by_employee.get(employee.id, {})
            vals = {
                field_name: value
                for field_name, value in incoming.items()
                if not employee[field_name]
            }
            if vals:
                employee.with_context(rail_skip_imss_employee_refresh=True).write(vals)
                touched |= employee

        if touched:
            touched.mapped('rail_imss_incidence_ids').filtered(
                lambda event: event.automatic and event.state != 'cancel'
            )._rail_refresh_automatic_state()
        return True

    @api.depends('rail_imss_incidence_ids')
    def _compute_rail_imss_incidence_count(self):
        grouped = dict(self.env['rail.imss.incidence']._read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'],
            ['__count'],
        )) if self.ids else {}
        for employee in self:
            employee.rail_imss_incidence_count = grouped.get(employee, 0)

    def action_open_rail_imss_incidents(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'rail_l10n_mx_payroll_imss.rail_imss_incidence_action'
        )
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {
            'default_employee_id': self.id,
            'default_version_id': self.version_id.id,
        }
        return action

    def action_rail_sync_imss_incidents(self):
        """Reconstruye eventos IMSS faltantes a partir del historial hr.version.

        Se ejecuta de forma explícita para datos ya migrados, evitando generar
        automáticamente una avalancha de movimientos al actualizar el módulo.
        """
        incidence_model = self.env['rail.imss.incidence']
        before_ids = set(incidence_model.search([
            ('employee_id', 'in', self.ids),
            ('state', '!=', 'cancel'),
        ]).ids)

        for employee in self:
            versions = employee.with_context(active_test=False).version_ids.filtered(
                lambda version: version.contract_date_start
            ).sorted(lambda version: (version.contract_date_start, version.date_version, version.id))
            contracts = defaultdict(lambda: self.env['hr.version'])
            for version in versions:
                contracts[version.contract_date_start] |= version

            for contract_index, contract_start in enumerate(sorted(contracts)):
                contract_versions = contracts[contract_start].sorted(lambda version: (version.date_version, version.id))
                first_version = contract_versions[0]
                incidence_type = 'hire' if contract_index == 0 else 'reentry'
                origin = 'contract_creation' if incidence_type == 'hire' else 'reentry'
                incidence_model.rail_get_or_create_event(
                    employee=employee,
                    version=first_version,
                    event_date=contract_start,
                    incidence_type=incidence_type,
                    origin=origin,
                    values={
                        'new_wage': first_version.wage,
                        'new_sbc': first_version.rail_fixed_sbc,
                        'note': _('Evento reconstruido desde el historial de versiones laborales.'),
                    },
                    automatic=True,
                )

                previous_version = first_version
                for version in contract_versions[1:]:
                    wage_changed = (
                        float_compare(previous_version.wage or 0.0, version.wage or 0.0, precision_digits=2) != 0
                        or float_compare(previous_version.hourly_wage or 0.0, version.hourly_wage or 0.0, precision_digits=2) != 0
                    )
                    sbc_changed = float_compare(
                        previous_version.rail_fixed_sbc or 0.0,
                        version.rail_fixed_sbc or 0.0,
                        precision_digits=6,
                    ) != 0
                    if wage_changed or sbc_changed:
                        origin = (
                            'wage_and_sbc_change' if wage_changed and sbc_changed
                            else 'wage_change' if wage_changed
                            else 'sbc_change'
                        )
                        incidence_model.rail_get_or_create_event(
                            employee=employee,
                            version=version,
                            event_date=version.date_version,
                            incidence_type='salary_change',
                            origin=origin,
                            values={
                                'old_wage': previous_version.wage,
                                'new_wage': version.wage,
                                'old_sbc': previous_version.rail_fixed_sbc,
                                'new_sbc': version.rail_fixed_sbc,
                                'wage_changed': wage_changed,
                                'sbc_changed': sbc_changed,
                                'note': _('Cambio reconstruido desde el historial de versiones laborales.'),
                            },
                            automatic=True,
                        )
                    previous_version = version

            if employee.departure_date:
                version = employee._get_version(employee.departure_date)
                if version:
                    incidence_model.rail_get_or_create_event(
                        employee=employee,
                        version=version,
                        event_date=employee.departure_date,
                        incidence_type='leave',
                        origin='departure',
                        values={
                            'old_wage': version.wage,
                            'new_wage': 0.0,
                            'old_sbc': version.rail_fixed_sbc,
                            'new_sbc': 0.0,
                            'note': _('Baja reconstruida desde la fecha de salida del empleado.'),
                        },
                        automatic=True,
                    )

            employee.rail_imss_incidence_ids.filtered(
                lambda event: event.automatic and event.state != 'cancel'
            )._rail_refresh_automatic_state()

        after_ids = set(incidence_model.search([
            ('employee_id', 'in', self.ids),
            ('state', '!=', 'cancel'),
        ]).ids)
        created_count = len(after_ids - before_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización IMSS'),
                'message': _(
                    'Se revisaron %(employees)s empleado(s) y se crearon %(events)s incidencia(s) faltante(s).'
                ) % {'employees': len(self), 'events': created_count},
                'type': 'success',
                'sticky': False,
            },
        }

    def rail_get_imss_identifier_values(self):
        self.ensure_one()
        return {
            'registration_number': self.registration_number or '',
            'ssn': self.ssnid or '',
            'rfc': self.l10n_mx_rfc or '',
            'curp': self.l10n_mx_curp or '',
            'zip': self.private_zip or '',
            'imss_clinic': self.rail_imss_clinic or '',
            'subdelegation_code': self.rail_imss_subdelegation_code or '',
            'worker_type': self.rail_imss_worker_type or '',
            'salary_type': self.rail_imss_salary_type or '',
            'workday_type': self.rail_imss_workday_type or '',
        }


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    rail_imss_clinic = fields.Char(compute='_compute_rail_imss_public_fields')
    rail_imss_subdelegation_code = fields.Char(compute='_compute_rail_imss_public_fields')
    rail_imss_worker_type = fields.Selection([
        ('1', '1 - Trabajador permanente'),
        ('2', '2 - Trabajador eventual en ciudad'),
        ('3', '3 - Trabajador eventual en construcción'),
        ('4', '4 - Eventual de campo'),
    ], compute='_compute_rail_imss_public_fields')
    rail_imss_salary_type = fields.Selection([
        ('0', '0 - Salario fijo'),
        ('1', '1 - Salario variable'),
        ('2', '2 - Salario mixto'),
    ], compute='_compute_rail_imss_public_fields')
    rail_imss_workday_type = fields.Selection([
        ('1', '1 - Un día'),
        ('2', '2 - Dos días'),
        ('3', '3 - Tres días'),
        ('4', '4 - Cuatro días'),
        ('5', '5 - Cinco días'),
        ('6', '6 - Jornada reducida'),
        ('0', '0 - Jornada normal'),
    ], compute='_compute_rail_imss_public_fields')

    def _compute_rail_imss_public_fields(self):
        self._compute_from_employee([
            'rail_imss_clinic',
            'rail_imss_subdelegation_code',
            'rail_imss_worker_type',
            'rail_imss_salary_type',
            'rail_imss_workday_type',
        ])
