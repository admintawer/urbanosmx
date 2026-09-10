# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RailImssIncidence(models.Model):
    _name = 'rail.imss.incidence'
    _description = 'Incidencia IMSS/SUA/IDSE'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Nuevo', copy=False, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, index=True)
    version_id = fields.Many2one(
        'hr.version',
        string='Versión laboral',
        required=True,
        domain="[('employee_id', '=', employee_id)]",
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    date = fields.Date(
        string='Fecha de movimiento',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    incidence_type = fields.Selection([
        ('hire', 'Alta'),
        ('reentry', 'Reingreso'),
        ('leave', 'Baja'),
        ('salary_change', 'Cambio salario'),
        ('register_change', 'Cambio registro patronal'),
    ], string='Tipo de incidencia', required=True, tracking=True, index=True)
    origin = fields.Selection([
        ('manual', 'Manual'),
        ('contract_creation', 'Creación de contrato/primera versión'),
        ('reentry', 'Reingreso'),
        ('departure', 'Baja de empleado'),
        ('wage_change', 'Cambio de salario'),
        ('sbc_change', 'Cambio manual de SBC'),
        ('sbc_bimonthly', 'SBC bimestral'),
        ('wage_and_sbc_change', 'Cambio de salario y SBC'),
        ('migration', 'Migración'),
    ], string='Origen', default='manual', required=True, tracking=True)
    automatic = fields.Boolean(
        string='Generada automáticamente',
        default=False,
        readonly=True,
        copy=False,
    )
    wage_changed = fields.Boolean(string='Cambió salario', readonly=True, copy=False)
    sbc_changed = fields.Boolean(string='Cambió SBC', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Confirmada'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='draft', required=True, tracking=True, index=True)
    old_sbc = fields.Float(string='SBC anterior', digits='Payroll')
    new_sbc = fields.Float(string='SBC nuevo', digits='Payroll')
    old_wage = fields.Monetary(string='Salario anterior')
    new_wage = fields.Monetary(string='Salario nuevo')
    currency_id = fields.Many2one('res.currency', related='version_id.currency_id')
    note = fields.Text(string='Notas')
    exported_sua = fields.Boolean(string='Exportado SUA', copy=False)
    exported_idse = fields.Boolean(string='Exportado IDSE', copy=False)

    _rail_unique_active_event = models.UniqueIndex(
        "(employee_id, version_id, incidence_type, date) WHERE state != 'cancel'",
        'Ya existe una incidencia IMSS activa del mismo tipo para esta versión y fecha.',
    )

    @api.model
    def _rail_get_first_versions_by_employee(
        self,
        company_ids=None,
        employee_ids=None,
        include_inactive=True,
    ):
        """Devuelve la primera versión histórica de cada empleado.

        Se prioriza ``contract_date_start`` y se usa ``date_version`` como
        respaldo para bases migradas donde la fecha inicial contractual no fue
        poblada. La lectura incluye versiones y empleados archivados cuando se
        solicita, requisito común en migraciones de v16/v18.
        """
        all_company_ids = self.env['res.company'].sudo().search([]).ids
        employee_domain = [('company_id', 'in', company_ids or all_company_ids)]
        if employee_ids:
            employee_domain.append(('id', 'in', employee_ids))
        employee_model = self.env['hr.employee'].with_context(active_test=not include_inactive)
        employees = employee_model.search(employee_domain)
        if not employees:
            return employees, {}

        versions = self.env['hr.version'].with_context(active_test=False).search([
            ('employee_id', 'in', employees.ids),
            '|',
            ('contract_date_start', '!=', False),
            ('date_version', '!=', False),
        ], order='employee_id, contract_date_start, date_version, id')

        first_versions = {}
        for version in versions:
            event_date = version.contract_date_start or version.date_version
            if not event_date:
                continue
            current = first_versions.get(version.employee_id.id)
            if not current:
                first_versions[version.employee_id.id] = version
                continue
            current_date = current.contract_date_start or current.date_version
            candidate_key = (event_date, version.date_version or event_date, version.id)
            current_key = (current_date, current.date_version or current_date, current.id)
            if candidate_key < current_key:
                first_versions[version.employee_id.id] = version
        return employees, first_versions

    @api.model
    def rail_backfill_retroactive_hires(
        self,
        company_ids=None,
        employee_ids=None,
        include_inactive=True,
        date_from=None,
        date_to=None,
    ):
        """Reconstruye altas IMSS desde la primera ``hr.version``.

        El proceso es idempotente: si el empleado ya tiene un Alta activa, no
        crea otra aunque el registro existente provenga de una migración o esté
        ligado a otra versión. Los eventos incompletos se conservan en borrador
        para que el funcional complete los datos IMSS faltantes.
        """
        self = self.sudo()
        date_from = fields.Date.to_date(date_from) if date_from else False
        date_to = fields.Date.to_date(date_to) if date_to else False
        employees, first_versions = self._rail_get_first_versions_by_employee(
            company_ids=company_ids,
            employee_ids=employee_ids,
            include_inactive=include_inactive,
        )

        stats = {
            'reviewed': len(employees),
            'created': 0,
            'existing': 0,
            'missing_date': 0,
            'confirmed': 0,
            'draft': 0,
        }
        if not employees:
            return stats

        existing_hires = self.search([
            ('employee_id', 'in', employees.ids),
            ('incidence_type', '=', 'hire'),
            ('state', '!=', 'cancel'),
        ])
        existing_by_employee = {event.employee_id.id: event for event in existing_hires}

        for employee in employees:
            existing = existing_by_employee.get(employee.id)
            if existing:
                existing._rail_refresh_automatic_state()
                stats['existing'] += 1
                stats['confirmed' if existing.state == 'done' else 'draft'] += 1
                continue

            version = first_versions.get(employee.id)
            if not version:
                stats['missing_date'] += 1
                continue
            event_date = version.contract_date_start or version.date_version
            if not event_date:
                stats['missing_date'] += 1
                continue
            if date_from and event_date < date_from:
                continue
            if date_to and event_date > date_to:
                continue

            event = self.rail_get_or_create_event(
                employee=employee,
                version=version,
                event_date=event_date,
                incidence_type='hire',
                origin='migration',
                values={
                    'old_wage': 0.0,
                    'new_wage': version.wage,
                    'old_sbc': 0.0,
                    'new_sbc': version.rail_fixed_sbc,
                    'note': _(
                        'Alta reconstruida retroactivamente desde la primera '
                        'versión laboral histórica del empleado.'
                    ),
                },
                automatic=True,
            )
            if event:
                stats['created'] += 1
                stats['confirmed' if event.state == 'done' else 'draft'] += 1
        return stats

    @api.model
    def _rail_backfill_hires_on_module_update(self):
        """Backfill único ejecutado al incorporar esta versión del módulo."""
        self.sudo().rail_backfill_retroactive_hires(include_inactive=True)
        return True

    @api.onchange('employee_id', 'date')
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id and not rec.version_id:
                rec.version_id = rec.employee_id._get_version(rec.date or fields.Date.today())

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = sequence.next_by_code('rail.imss.incidence') or 'Nuevo'
        records = super().create(vals_list)
        automatic_records = records.filtered('automatic')
        if automatic_records:
            automatic_records._rail_refresh_automatic_state()
        return records

    def action_confirm(self):
        for rec in self:
            missing = rec._rail_get_missing_required_data()
            if missing:
                raise UserError(
                    _('No se puede confirmar %(incidence)s. Faltan: %(missing)s') % {
                        'incidence': rec.display_name,
                        'missing': ', '.join(missing),
                    }
                )
            rec.state = 'done'

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _validate_required_data(self):
        """Compatibilidad con llamadas existentes del módulo."""
        for rec in self:
            missing = rec._rail_get_missing_required_data()
            if missing:
                raise UserError(
                    _('Faltan datos IMSS/SUA para %(employee)s: %(fields)s') % {
                        'employee': rec.employee_id.display_name,
                        'fields': ', '.join(missing),
                    }
                )

    def _rail_get_missing_required_data(self):
        self.ensure_one()
        missing = []
        version = self.version_id
        employee = self.employee_id

        if not employee.ssnid:
            missing.append(_('NSS'))
        if not self.company_id.l10n_mx_imss_id:
            missing.append(_('Registro patronal de la compañía'))

        if self.incidence_type in ('hire', 'reentry'):
            if not employee.rail_imss_worker_type:
                missing.append(_('Tipo de trabajador'))
            if not employee.rail_imss_salary_type:
                missing.append(_('Tipo de salario'))
            if not employee.rail_imss_workday_type:
                missing.append(_('Tipo de jornada'))
            if not employee.rail_imss_clinic:
                missing.append(_('Unidad de medicina familiar'))
            if not employee.private_zip:
                missing.append(_('Código postal del trabajador'))

        if self.incidence_type in ('hire', 'reentry', 'salary_change'):
            effective_sbc = self.new_sbc or version.rail_fixed_sbc
            if not effective_sbc:
                missing.append(_('SBC vigente'))

        if self.incidence_type == 'salary_change' and not (self.wage_changed or self.sbc_changed):
            missing.append(_('Indicador de cambio de salario o SBC'))

        return missing

    def _rail_refresh_automatic_state(self):
        """Confirma eventos automáticos completos y deja en borrador los incompletos."""
        for rec in self.filtered(lambda item: item.automatic and item.state != 'cancel'):
            target_state = 'draft' if rec._rail_get_missing_required_data() else 'done'
            if rec.state != target_state:
                rec.with_context(tracking_disable=True).write({'state': target_state})
        return True

    @api.model
    def _rail_merge_origin(self, current_origin, incoming_origin, wage_changed=False, sbc_changed=False):
        if wage_changed and sbc_changed:
            return 'wage_and_sbc_change'
        salary_origins = {
            'wage_change', 'sbc_change', 'sbc_bimonthly', 'wage_and_sbc_change',
        }
        if current_origin in salary_origins and incoming_origin in salary_origins and current_origin != incoming_origin:
            return 'wage_and_sbc_change'
        return incoming_origin or current_origin or 'manual'

    @api.model
    def rail_get_or_create_event(
        self,
        employee,
        version,
        event_date,
        incidence_type,
        origin='manual',
        values=None,
        automatic=True,
    ):
        """Crea o actualiza un movimiento IMSS sin duplicarlo.

        La llave funcional es empleado + versión + tipo + fecha. Si el cambio de
        wage y el cambio de SBC llegan por flujos distintos para la misma versión,
        ambos se consolidan en una sola incidencia salary_change.
        """
        if not employee or not version or not event_date:
            return self.browse()
        event_date = fields.Date.to_date(event_date)
        values = dict(values or {})
        domain = [
            ('employee_id', '=', employee.id),
            ('version_id', '=', version.id),
            ('incidence_type', '=', incidence_type),
            ('date', '=', event_date),
            ('state', '!=', 'cancel'),
        ]
        event = self.search(domain, limit=1)

        wage_changed = bool(values.get('wage_changed')) or bool(event.wage_changed)
        sbc_changed = bool(values.get('sbc_changed')) or bool(event.sbc_changed)
        merged_origin = self._rail_merge_origin(
            event.origin if event else False,
            origin,
            wage_changed=wage_changed,
            sbc_changed=sbc_changed,
        )

        vals = {
            'employee_id': employee.id,
            'version_id': version.id,
            'date': event_date,
            'incidence_type': incidence_type,
            'origin': merged_origin,
            'automatic': automatic,
            **values,
            'wage_changed': wage_changed,
            'sbc_changed': sbc_changed,
        }
        # No vaciar valores previamente registrados al consolidar dos orígenes.
        for field_name in ('old_sbc', 'new_sbc', 'old_wage', 'new_wage', 'note'):
            if event and not vals.get(field_name) and event[field_name]:
                vals[field_name] = event[field_name]

        if event:
            event.write(vals)
        else:
            event = self.create(vals)
        if automatic:
            event._rail_refresh_automatic_state()
        return event
