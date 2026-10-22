# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # Proxies de compatibilidad: los datos SUA/IDSE son permanentes del
    # trabajador y se almacenan físicamente en hr.employee.
    rail_imss_clinic = fields.Char(
        related='employee_id.rail_imss_clinic',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    rail_imss_subdelegation_code = fields.Char(
        related='employee_id.rail_imss_subdelegation_code',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    rail_imss_worker_type = fields.Selection(
        related='employee_id.rail_imss_worker_type',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    rail_imss_salary_type = fields.Selection(
        related='employee_id.rail_imss_salary_type',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )
    rail_imss_workday_type = fields.Selection(
        related='employee_id.rail_imss_workday_type',
        readonly=False,
        groups='hr_payroll.group_hr_payroll_user',
    )

    rail_sbc_effective_date = fields.Date(
        string='Fecha efectiva SBC',
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
        help='Fecha efectiva del SBC manual generado por cálculo bimestral.',
    )
    rail_previous_sbc = fields.Float(
        string='SBC anterior',
        digits='Payroll',
        groups='hr_payroll.group_hr_payroll_user',
        tracking=True,
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        fields_list = super()._get_whitelist_fields_from_template() or []
        fields_list += [
            'rail_fixed_sbc',
            'rail_sbc_effective_date',
            'rail_previous_sbc',
        ]
        return fields_list

    @api.model_create_multi
    def create(self, vals_list):
        versions = super().create(vals_list)
        if self.env.context.get('rail_skip_imss_auto_incidence'):
            return versions

        versions._rail_sync_contract_event()
        for version in versions:
            previous_version = version._rail_get_previous_version_same_contract()
            if not previous_version:
                continue
            version._rail_register_salary_change({
                'wage': previous_version.wage,
                'hourly_wage': previous_version.hourly_wage,
                'rail_fixed_sbc': previous_version.rail_fixed_sbc,
                'contract_date_start': previous_version.contract_date_start,
            })
        return versions

    def write(self, vals):
        skip_automatic = self.env.context.get('rail_skip_imss_auto_incidence')
        sync_contract_dates = self.env.context.get('sync_contract_dates')
        watched_salary = {'wage', 'hourly_wage', 'rail_fixed_sbc'}
        watched_contract = {'employee_id', 'contract_date_start', 'date_version'}
        watched_required = {'ssnid', 'rail_fixed_sbc'}

        old_values = {
            version.id: {
                'wage': version.wage,
                'hourly_wage': version.hourly_wage,
                'rail_fixed_sbc': version.rail_fixed_sbc,
                'contract_date_start': version.contract_date_start,
            }
            for version in self
        }
        result = super().write(vals)

        if skip_automatic:
            return result

        if watched_contract.intersection(vals) and not sync_contract_dates:
            self._rail_sync_contract_event()

        if watched_salary.intersection(vals):
            for version in self:
                version._rail_register_salary_change(old_values.get(version.id, {}))

        if watched_required.intersection(vals):
            self.mapped('employee_id.rail_imss_incidence_ids').filtered(
                lambda event: event.automatic and event.state != 'cancel'
            )._rail_refresh_automatic_state()

        return result

    def _rail_get_previous_version_same_contract(self):
        self.ensure_one()
        if not self.employee_id or not self.contract_date_start:
            return self.env['hr.version']
        return self.with_context(active_test=False).search([
            ('employee_id', '=', self.employee_id.id),
            ('contract_date_start', '=', self.contract_date_start),
            ('date_version', '<', self.date_version),
        ], order='date_version desc, id desc', limit=1)

    def _rail_sync_contract_event(self):
        incidence_model = self.env['rail.imss.incidence']
        for version in self.filtered(lambda item: item.employee_id and item.contract_date_start):
            employee = version.employee_id
            contract_versions = employee.with_context(active_test=False).version_ids.filtered(
                lambda item: item.contract_date_start == version.contract_date_start
            ).sorted(lambda item: (item.date_version, item.id))
            if not contract_versions or version != contract_versions[0]:
                continue

            previous_contracts = employee.with_context(active_test=False).version_ids.filtered(
                lambda item: item.contract_date_start and item.contract_date_start < version.contract_date_start
            )
            previous_leave = incidence_model.search_count([
                ('employee_id', '=', employee.id),
                ('incidence_type', '=', 'leave'),
                ('date', '<', version.contract_date_start),
                ('state', '!=', 'cancel'),
            ])
            incidence_type = 'reentry' if previous_contracts or previous_leave else 'hire'
            origin = 'reentry' if incidence_type == 'reentry' else 'contract_creation'
            note = (
                _('Evento generado automáticamente por inicio de un nuevo contrato laboral.')
                if incidence_type == 'reentry'
                else _('Evento generado automáticamente por creación del primer contrato laboral.')
            )
            incidence_model.rail_get_or_create_event(
                employee=employee,
                version=version,
                event_date=version.contract_date_start,
                incidence_type=incidence_type,
                origin=origin,
                values={
                    'old_wage': 0.0,
                    'new_wage': version.wage,
                    'old_sbc': 0.0,
                    'new_sbc': version.rail_fixed_sbc,
                    'note': note,
                },
                automatic=True,
            )
        return True

    def _rail_register_salary_change(self, old_values):
        self.ensure_one()
        old_wage = old_values.get('wage') or 0.0
        old_hourly_wage = old_values.get('hourly_wage') or 0.0
        old_sbc = old_values.get('rail_fixed_sbc') or 0.0
        current_wage = self.wage or 0.0
        current_hourly_wage = self.hourly_wage or 0.0
        current_sbc = self.rail_fixed_sbc or 0.0

        wage_changed = (
            float_compare(old_wage, current_wage, precision_digits=2) != 0
            or float_compare(old_hourly_wage, current_hourly_wage, precision_digits=2) != 0
        )
        sbc_changed = float_compare(old_sbc, current_sbc, precision_digits=6) != 0
        force_change = bool(self.env.context.get('rail_imss_force_salary_change'))
        if not (wage_changed or sbc_changed or force_change):
            return self.env['rail.imss.incidence']

        # La captura inicial del salario/SBC del primer registro contractual forma
        # parte del Alta/Reingreso; no debe crear un segundo movimiento de cambio.
        previous_same_contract = self._rail_get_previous_version_same_contract()
        initial_contract_event = self.env['rail.imss.incidence'].search([
            ('employee_id', '=', self.employee_id.id),
            ('version_id', '=', self.id),
            ('incidence_type', 'in', ['hire', 'reentry']),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if not force_change and not previous_same_contract and initial_contract_event and not old_wage and not old_sbc:
            initial_contract_event.write({
                'new_wage': current_wage,
                'new_sbc': current_sbc,
            })
            initial_contract_event._rail_refresh_automatic_state()
            return initial_contract_event

        origin = self.env.context.get('rail_imss_incidence_origin')
        if not origin:
            if wage_changed and sbc_changed:
                origin = 'wage_and_sbc_change'
            elif sbc_changed:
                origin = 'sbc_change'
            else:
                origin = 'wage_change'

        event_date = self.env.context.get('rail_imss_effective_date') or self.date_version
        note = self.env.context.get('rail_imss_incidence_note')
        if not note:
            if origin == 'sbc_bimonthly':
                note = _('Cambio generado desde el cálculo SBC bimestral.')
            elif wage_changed and sbc_changed:
                note = _('Cambio automático de salario y SBC en la versión laboral.')
            elif sbc_changed:
                note = _('Cambio automático de SBC en la versión laboral.')
            else:
                note = _('Cambio automático de salario en la versión laboral.')

        return self.env['rail.imss.incidence'].rail_get_or_create_event(
            employee=self.employee_id,
            version=self,
            event_date=event_date,
            incidence_type='salary_change',
            origin=origin,
            values={
                'old_wage': old_wage,
                'new_wage': current_wage,
                'old_sbc': old_sbc,
                'new_sbc': current_sbc,
                'wage_changed': wage_changed,
                'sbc_changed': sbc_changed or force_change,
                'note': note,
            },
            automatic=True,
        )
