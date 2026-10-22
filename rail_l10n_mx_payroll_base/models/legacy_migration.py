# -*- coding: utf-8 -*-

import logging

from psycopg2 import sql

from odoo import api, Command, fields, models


_logger = logging.getLogger(__name__)


class RailPayrollMigrationArchive(models.Model):
    """Immutable source snapshots used to audit a v16 -> v19 payroll migration."""

    _name = 'rail.payroll.migration.archive'
    _description = 'Archivo de migración de nómina legacy'
    _order = 'source_module, source_table, source_id'

    source_module = fields.Char(required=True, index=True)
    source_table = fields.Char(required=True, index=True)
    source_id = fields.Integer(required=True, index=True)
    target_model = fields.Char(index=True)
    target_id = fields.Integer(index=True)
    payload = fields.Json(required=True)
    migration_note = fields.Text()
    migrated_at = fields.Datetime(default=fields.Datetime.now, required=True)

    _source_row_unique = models.Constraint(
        'UNIQUE(source_module, source_table, source_id)',
        'La fila legacy ya fue archivada.',
    )


class RailPayrollLegacyMigration(models.AbstractModel):
    """Idempotent SQL migration helpers for the deprecated payroll modules.

    The Odoo upgrade service may rename ``hr_contract`` to ``hr_version`` while
    preserving custom columns.  Every operation therefore inspects the live
    schema and skips absent columns instead of assuming one exact intermediate
    upgrade layout.
    """

    _name = 'rail.payroll.legacy.migration'
    _description = 'Migración de datos de nómina legacy'

    _BASE_ARCHIVE_TABLES = {
        'hr_version': 'hr.version',
        'hr_contract': 'hr.version',
        'hr_employee': 'hr.employee',
        'hr_salary_rule': 'hr.salary.rule',
        'hr_payslip': 'hr.payslip',
        'hr_payslip_run': 'hr.payslip.run',
        'res_company': 'res.company',
        'res_bank': 'res.bank',
        'tablas_cfdi': False,
        'tablas_antiguedades_line': False,
        'tablas_general_line': False,
        'tablas_subsidio_line': False,
        'tablas_subsidio2_line': False,
        'tablas_subsidioacreditable_line': False,
        'tablas_periodo_bimestral': False,
        'tablas_periodo_mensual': False,
        'tablas_periodo_semanal': False,
        'tablas_isr_anual': False,
        'tablas_vacaciones_line': False,
        'nomina_deduccion': False,
        'nomina_percepcion': False,
        'nomina_otropago': False,
        'horas_nomina': False,
        'configuracion_nomina': False,
        'otras_entradas': False,
    }

    _EXTRAS_ARCHIVE_TABLES = {
        'employee_loan': 'employee.loan',
        'employee_loan_type': 'employee.loan.type',
        'installment_line': 'installment.line',
        'viaticos_nomina': 'viaticos.nomina',
        'entregas_viaticos_nomina': 'entregas.viaticos.nomina',
        'comprobaciones_viaticos_nomina': 'comprobaciones.viaticos.nomina',
        'faltas_nomina': False,
        'incapacidades_nomina': False,
        'incidencias_nomina': 'rail.imss.incidence',
        'retardo_nomina': False,
        'vacaciones_nomina': False,
        'dias_feriados': False,
        'contract_historial_salario': 'hr.version',
        'dev_skip_installment': 'installment.line',
    }

    @api.model
    def _table_exists(self, table):
        self.env.cr.execute('SELECT to_regclass(%s)', (table,))
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _columns(self, table):
        if not self._table_exists(table):
            return {}
        self.env.cr.execute(
            """
            SELECT column_name, data_type
              FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = %s
            """,
            (table,),
        )
        return dict(self.env.cr.fetchall())

    @api.model
    def _archive_table(self, source_module, table, target_model=False):
        columns = self._columns(table)
        if 'id' not in columns:
            return 0
        query = sql.SQL(
            """
            INSERT INTO rail_payroll_migration_archive
                (source_module, source_table, source_id, target_model, target_id,
                 payload, migration_note, migrated_at, create_uid, create_date, write_uid, write_date)
            SELECT %s, %s, source.id, %s, source.id, to_jsonb(source), %s,
                   NOW(), %s, NOW(), %s, NOW()
              FROM {table} AS source
            ON CONFLICT (source_module, source_table, source_id)
            DO UPDATE SET payload = EXCLUDED.payload,
                          target_model = EXCLUDED.target_model,
                          target_id = EXCLUDED.target_id,
                          migration_note = EXCLUDED.migration_note,
                          migrated_at = EXCLUDED.migrated_at,
                          write_uid = EXCLUDED.write_uid,
                          write_date = EXCLUDED.write_date
            """
        ).format(table=sql.Identifier(table))
        note = 'Copia íntegra previa a la transformación v16 -> v19'
        self.env.cr.execute(
            query,
            (source_module, table, target_model or None, note, self.env.uid, self.env.uid),
        )
        return self.env.cr.rowcount

    @api.model
    def _copy_columns(self, table, mapping):
        """Copy legacy columns without overwriting an already populated target."""
        columns = self._columns(table)
        copied = {}
        for source, target in mapping.items():
            if source not in columns or target not in columns or source == target:
                continue
            target_type = columns[target]
            if target_type == 'boolean':
                empty_target = sql.SQL('({target} IS NULL OR {target} = FALSE)').format(
                    target=sql.Identifier(target),
                )
            elif target_type in ('smallint', 'integer', 'bigint', 'numeric', 'real', 'double precision'):
                empty_target = sql.SQL('({target} IS NULL OR {target} = 0)').format(
                    target=sql.Identifier(target),
                )
            else:
                empty_target = sql.SQL("({target} IS NULL OR {target}::text = '')").format(
                    target=sql.Identifier(target),
                )
            query = sql.SQL(
                "UPDATE {table} SET {target} = {source} "
                "WHERE {source} IS NOT NULL AND {empty_target}"
            ).format(
                table=sql.Identifier(table),
                target=sql.Identifier(target),
                source=sql.Identifier(source),
                empty_target=empty_target,
            )
            self.env.cr.execute(query)
            copied['%s->%s' % (source, target)] = self.env.cr.rowcount
        return copied

    @api.model
    def _copy_selection(self, table, source, target, value_mapping, replace_defaults=()):
        columns = self._columns(table)
        if source not in columns or target not in columns:
            return 0
        cases = []
        params = []
        for old_value, new_value in value_mapping.items():
            cases.append('WHEN %s THEN %s')
            params.extend((old_value, new_value))
        target_condition = sql.SQL("({target} IS NULL OR {target}::text = '')").format(
            target=sql.Identifier(target),
        )
        if replace_defaults:
            target_condition = sql.SQL('({base} OR {target} = ANY(%s))').format(
                base=target_condition,
                target=sql.Identifier(target),
            )
        query = sql.SQL(
            "UPDATE {table} SET {target} = CASE {source} {cases} ELSE {target} END "
            "WHERE {source} = ANY(%s) AND {target_condition}"
        ).format(
            table=sql.Identifier(table),
            target=sql.Identifier(target),
            source=sql.Identifier(source),
            cases=sql.SQL(' ').join(map(sql.SQL, cases)),
            target_condition=target_condition,
        )
        params.append(list(value_mapping))
        if replace_defaults:
            params.append(list(replace_defaults))
        self.env.cr.execute(query, params)
        return self.env.cr.rowcount

    @api.model
    def _archive_many(self, source_module, tables):
        result = {}
        for table, target_model in tables.items():
            count = self._archive_table(source_module, table, target_model)
            if count:
                result[table] = count
        return result

    @api.model
    def _copy_unique_employee_registration_numbers(self):
        """Copy legacy employee numbers without violating the v19 constraint.

        Odoo 16 allowed ``no_empleado`` to be repeated.  Odoo 19 enforces one
        ``registration_number`` per company.  A duplicated business identifier
        must be resolved by the customer, so the migration archives and flags
        every ambiguous row instead of choosing an employee or inventing a new
        number.
        """
        columns = self._columns('hr_employee')
        required = {'id', 'company_id', 'no_empleado', 'registration_number'}
        if not required.issubset(columns):
            return {'copied': 0, 'duplicate_source_rows': 0, 'target_conflict_rows': 0}

        self.env.cr.execute(
            """
            WITH candidates AS (
                SELECT id,
                       company_id,
                       NULLIF(BTRIM(no_empleado::text), '') AS legacy_number
                  FROM hr_employee
            ), duplicate_groups AS (
                SELECT company_id, legacy_number
                  FROM candidates
                 WHERE legacy_number IS NOT NULL
              GROUP BY company_id, legacy_number
                HAVING COUNT(*) > 1
            )
            SELECT ARRAY_AGG(candidate.id ORDER BY candidate.id)
              FROM candidates AS candidate
              JOIN duplicate_groups AS duplicate_group
                ON duplicate_group.company_id IS NOT DISTINCT FROM candidate.company_id
               AND duplicate_group.legacy_number = candidate.legacy_number
            """
        )
        duplicate_ids = (self.env.cr.fetchone()[0] or [])

        self.env.cr.execute(
            """
            WITH candidates AS (
                SELECT employee.id,
                       employee.company_id,
                       NULLIF(BTRIM(employee.no_empleado::text), '') AS legacy_number
                  FROM hr_employee AS employee
            )
            SELECT ARRAY_AGG(candidate.id ORDER BY candidate.id)
              FROM candidates AS candidate
             WHERE candidate.legacy_number IS NOT NULL
               AND EXISTS (
                    SELECT 1
                      FROM hr_employee AS other
                     WHERE other.id != candidate.id
                       AND other.company_id IS NOT DISTINCT FROM candidate.company_id
                       AND NULLIF(BTRIM(other.registration_number), '') = candidate.legacy_number
               )
            """
        )
        target_conflict_ids = (self.env.cr.fetchone()[0] or [])
        conflict_ids = sorted(set(duplicate_ids) | set(target_conflict_ids))

        self.env.cr.execute(
            """
            WITH candidates AS (
                SELECT employee.id,
                       employee.company_id,
                       NULLIF(BTRIM(employee.no_empleado::text), '') AS legacy_number
                  FROM hr_employee AS employee
            ), safe_candidates AS (
                SELECT MIN(id) AS id, company_id, legacy_number
                  FROM candidates
                 WHERE legacy_number IS NOT NULL
              GROUP BY company_id, legacy_number
                HAVING COUNT(*) = 1
            )
            UPDATE hr_employee AS employee
               SET registration_number = safe.legacy_number
              FROM safe_candidates AS safe
             WHERE employee.id = safe.id
               AND NULLIF(BTRIM(employee.registration_number), '') IS NULL
               AND NOT EXISTS (
                    SELECT 1
                      FROM hr_employee AS other
                     WHERE other.id != employee.id
                       AND other.company_id IS NOT DISTINCT FROM employee.company_id
                       AND NULLIF(BTRIM(other.registration_number), '') = safe.legacy_number
               )
            """
        )
        copied = self.env.cr.rowcount

        if conflict_ids and self._table_exists('rail_payroll_migration_archive'):
            self.env.cr.execute(
                """
                UPDATE rail_payroll_migration_archive
                   SET migration_note = CONCAT_WS(
                        E'\n',
                        NULLIF(migration_note, ''),
                        'No se copió no_empleado a registration_number: valor duplicado o en conflicto dentro de la compañía.'
                   ),
                       write_uid = %s,
                       write_date = NOW()
                 WHERE source_module = 'nomina_cfdi'
                   AND source_table = 'hr_employee'
                   AND source_id = ANY(%s)
                """,
                (self.env.uid, conflict_ids),
            )

        return {
            'copied': copied,
            'duplicate_source_rows': len(duplicate_ids),
            'target_conflict_rows': len(target_conflict_ids),
            'conflict_employee_ids': conflict_ids,
        }

    @api.model
    def run_nomina_cfdi(self):
        """Archive and map the safe, one-to-one fields from ``nomina_cfdi``."""
        result = {'archive': self._archive_many('nomina_cfdi', self._BASE_ARCHIVE_TABLES)}
        version_table = 'hr_version' if self._table_exists('hr_version') else 'hr_contract'
        result['hr_version'] = self._copy_columns(version_table, {
            'bono_productividad': 'rail_productivity_bonus',
            'bono_productividad_amount': 'rail_productivity_bonus_amount',
            'bono_asistencia': 'rail_attendance_bonus',
            'bono_asistencia_amount': 'rail_attendance_bonus_amount',
            'bono_puntualidad': 'rail_punctuality_bonus',
            'bono_puntualidad_amount': 'rail_punctuality_bonus_amount',
            'fondo_ahorro': 'rail_savings_fund',
            'fondo_ahorro_amount': 'rail_savings_fund_amount',
            'vale_despensa': 'rail_grocery_voucher',
            'vale_despensa_amount': 'rail_grocery_voucher_amount',
            'alimentacion': 'rail_food_allowance',
            'alimentacion_amount': 'rail_food_allowance_amount',
            'percepcion_adicional': 'rail_additional_perception',
            'percepcion_adicional_amount': 'rail_additional_perception_amount',
            'pens_alim': 'rail_alimony_percentage',
            'prestamo_fonacot': 'rail_fonacot_loan_amount',
            'caja_ahorro': 'rail_savings_bank',
            'caja_ahorro_amount': 'rail_savings_bank_amount',
            'deduccion_adicional': 'rail_additional_deduction',
            'deduccion_adicional_amount': 'rail_additional_deduction_amount',
            'sueldo_base_cotizacion': 'rail_fixed_sbc',
            'tipo_pago': 'rail_day_count_type',
            'tipo_prima_vacacional': 'rail_vacation_bonus_timing',
            'septimo_dia': 'rail_seventh_day',
            'incapa_sept_dia': 'rail_seventh_day_disability',
            'sept_dia': 'rail_seventh_day_discount',
            'semana_inglesa': 'rail_english_week',
            'prima_dominical': 'rail_sunday_bonus',
        })
        result['native_version'] = self._copy_columns(version_table, {
            'fondo_ahorro_amount': 'l10n_mx_savings_fund',
            'vale_despensa_amount': 'l10n_mx_meal_voucher_amount',
        })
        result['employee'] = self._copy_columns('hr_employee', {
            'rfc': 'l10n_mx_rfc',
            'curp': 'l10n_mx_curp',
            'correo_electronico': 'private_email',
        })
        result['employee_registration_number'] = self._copy_unique_employee_registration_numbers()
        result['employee_version'] = self._copy_employee_fields_to_versions()
        result['company'] = self._copy_columns('res_company', {
            'curp': 'l10n_mx_curp',
            'registro_patronal': 'l10n_mx_imss_id',
        })
        result['salary_rule'] = self._copy_columns('hr_salary_rule', {
            'variable_imss': 'rail_sbc_variable',
            'variable_imss_monto': 'rail_sbc_variable_amount',
        })
        result['salary_rule_type'] = self._copy_selection(
            'hr_salary_rule',
            'variable_imss_tipo',
            'rail_sbc_variable_type',
            {'001': 'all', '002': 'excess_uma', '003': 'excess_sbc'},
            replace_defaults=('all',),
        )
        result['bank'] = self._copy_columns('res_bank', {'c_banco': 'rail_mx_bank_code'})
        result['payslip_run'] = self._copy_columns('hr_payslip_run', {
            'no_nomina': 'rail_payroll_number',
        })
        result['payslip_run_type'] = self._copy_selection(
            'hr_payslip_run',
            'tipo_nomina',
            'rail_l10n_mx_payroll_type',
            {'O': 'O', 'E': 'E'},
            replace_defaults=('O',),
        )
        result['schedule_pay'] = self._copy_selection(version_table, 'periodicidad_pago', 'schedule_pay', {
            '01': 'daily',
            '02': 'weekly',
            '03': '14_days',
            '04': 'bi-weekly',
            '05': 'monthly',
            '06': 'bi-monthly',
            '10': '10_days',
        }, replace_defaults=('monthly',))
        result['native_credits'] = self._migrate_native_mx_credits(version_table)
        result['employee_bank_accounts'] = self._migrate_employee_bank_accounts()
        _logger.info('Resultado migración nomina_cfdi: %s', result)
        return result

    @api.model
    def _copy_employee_fields_to_versions(self):
        employee_columns = self._columns('hr_employee')
        version_columns = self._columns('hr_version')
        if 'employee_id' not in version_columns:
            return {}
        mapping = {
            'tipo_regimen': ('l10n_mx_regime_type', '02'),
            'jornada': ('l10n_mx_shift_type', '01'),
            'zip': ('private_zip', ''),
            'segurosocial': ('ssnid', ''),
        }
        result = {}
        for source, (target, default_value) in mapping.items():
            if source not in employee_columns or target not in version_columns:
                continue
            query = sql.SQL(
                "UPDATE hr_version AS version SET {target} = employee.{source} "
                "FROM hr_employee AS employee "
                "WHERE version.employee_id = employee.id "
                "AND employee.{source} IS NOT NULL "
                "AND (version.{target} IS NULL OR version.{target}::text = '' OR version.{target} = %s)"
            ).format(target=sql.Identifier(target), source=sql.Identifier(source))
            self.env.cr.execute(query, (default_value,))
            result['%s->%s' % (source, target)] = self.env.cr.rowcount
        return result

    @api.model
    def _migrate_native_mx_credits(self, version_table):
        """Create native INFONAVIT/FONACOT rows from unambiguous v16 amounts."""
        stats = {'infonavit': 0, 'fonacot': 0, 'skipped': 0}
        wanted = [
            'id', 'infonavit_fijo', 'infonavit_vsm', 'infonavit_porc',
            'prestamo_fonacot', 'employee_id', 'date_start',
        ]
        rows = self._fetch_dict_rows(version_table, wanted)
        Infonavit = (
            self.env['l10n.mx.hr.infonavit'].sudo()
            if 'l10n.mx.hr.infonavit' in self.env.registry else False
        )
        Fonacot = (
            self.env['l10n.mx.hr.fonacot'].sudo()
            if 'l10n.mx.hr.fonacot' in self.env.registry else False
        )
        Version = self.env['hr.version'].sudo().with_context(active_test=False)
        for row in rows:
            version = Version.browse(row['id']).exists()
            if not version and row.get('employee_id'):
                domain = [('employee_id', '=', row['employee_id'])]
                if row.get('date_start'):
                    domain.append(('contract_date_start', '=', row['date_start']))
                version = Version.search(domain, order='date_version desc, id desc', limit=1)
            if not version:
                stats['skipped'] += 1
                continue
            version_id = version.id
            fixed = float(row.get('infonavit_fijo') or 0.0)
            factor = float(row.get('infonavit_vsm') or 0.0)
            percentage = float(row.get('infonavit_porc') or 0.0)
            if Infonavit and (fixed or factor or percentage):
                if not Infonavit.search([('version_id', '=', version_id)], limit=1):
                    if fixed:
                        values = {'infonavit_type': 'fixed_monetary_fee', 'fixed_monetary_fee': fixed}
                    elif percentage:
                        values = {'infonavit_type': 'percentage', 'percentage': percentage}
                    else:
                        values = {'infonavit_type': 'discount_factor', 'discount_factor': factor}
                    Infonavit.create({'version_id': version_id, **values})
                    stats['infonavit'] += 1
            fonacot_amount = float(row.get('prestamo_fonacot') or 0.0)
            if Fonacot and fonacot_amount:
                if not Fonacot.search([('version_id', '=', version_id)], limit=1):
                    Fonacot.create({
                        'version_id': version_id,
                        'monthly_import': fonacot_amount,
                    })
                    stats['fonacot'] += 1
            if not Infonavit or not Fonacot:
                stats['skipped'] += 1
        return stats

    @api.model
    def _migrate_employee_bank_accounts(self):
        wanted = ['id', 'banco', 'no_cuenta', 'tipo_cuenta']
        rows = self._fetch_dict_rows('hr_employee', wanted)
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        PartnerBank = self.env['res.partner.bank'].sudo().with_context(active_test=False)
        type_mapping = {
            't_debido': 'debit_card',
            't_debito': 'debit_card',
            'cheques': 'checking',
            'c_ahorro': 'savings',
            't_credito': 'credit_card',
        }
        stats = {'created': 0, 'linked': 0, 'existing': 0, 'skipped': 0}
        for row in rows:
            account_number = (row.get('no_cuenta') or '').strip()
            employee = Employee.browse(row['id']).exists()
            if not employee or not account_number or not employee.work_contact_id:
                stats['skipped'] += 1
                continue
            account = PartnerBank.search([
                ('partner_id', '=', employee.work_contact_id.id),
                ('acc_number', '=', account_number),
            ], limit=1)
            if not account:
                values = {
                    'partner_id': employee.work_contact_id.id,
                    'acc_number': account_number,
                    'bank_id': row.get('banco') or False,
                    'company_id': employee.company_id.id,
                }
                account_type = type_mapping.get(row.get('tipo_cuenta'))
                if account_type and 'rail_mx_account_type' in PartnerBank._fields:
                    values['rail_mx_account_type'] = account_type
                account = PartnerBank.create(values)
                stats['created'] += 1
            else:
                stats['existing'] += 1
            if account not in employee.bank_account_ids:
                employee.write({'bank_account_ids': [Command.link(account.id)]})
                stats['linked'] += 1
        return stats

    @api.model
    def run_nomina_cfdi_extras(self):
        """Archive extras and backfill links required by the v19 replacement models."""
        result = {'archive': self._archive_many('nomina_cfdi_extras', self._EXTRAS_ARCHIVE_TABLES)}

        # Existing records keep the same model/table names in the replacement.
        # Populate newly introduced company links without overwriting migrated data.
        for table in ('employee_loan', 'viaticos_nomina'):
            columns = self._columns(table)
            if {'employee_id', 'company_id'} <= set(columns):
                query = sql.SQL(
                    "UPDATE {table} AS source SET company_id = employee.company_id "
                    "FROM hr_employee AS employee "
                    "WHERE source.employee_id = employee.id AND source.company_id IS NULL"
                ).format(table=sql.Identifier(table))
                self.env.cr.execute(query)
                result['%s_company' % table] = self.env.cr.rowcount

        # The v19 loan/viatic models resolve hr.version from employee/date.  This
        # ORM recomputation is deliberately non-destructive and can be rerun.
        for model_name in ('employee.loan', 'viaticos.nomina'):
            model = self.env[model_name].with_context(active_test=False).sudo()
            if 'version_id' in model._fields:
                records = model.search([('version_id', '=', False)])
                records._compute_version_id()
                result['%s_version' % model_name] = len(records)

        result['imss_incidence'] = self._migrate_imss_incidences()
        result['vacation_balance'] = self._migrate_vacation_balances()

        _logger.info('Resultado migración nomina_cfdi_extras: %s', result)
        return result

    @api.model
    def _fetch_dict_rows(self, table, wanted_columns):
        columns = self._columns(table)
        selected = [name for name in wanted_columns if name in columns]
        if 'id' not in selected:
            return []
        self.env.cr.execute(
            sql.SQL('SELECT {fields} FROM {table} ORDER BY id').format(
                fields=sql.SQL(', ').join(map(sql.Identifier, selected)),
                table=sql.Identifier(table),
            )
        )
        return [dict(zip(selected, row)) for row in self.env.cr.fetchall()]

    @api.model
    def _migrate_imss_incidences(self):
        if not self._table_exists('incidencias_nomina') or 'rail.imss.incidence' not in self.env.registry:
            return {'created': 0, 'existing': 0, 'skipped': 0}
        rows = self._fetch_dict_rows('incidencias_nomina', [
            'id', 'name', 'tipo_de_incidencia', 'employee_id', 'fecha', 'state',
            'registro_patronal', 'sueldo_mensual', 'sueldo_diario',
            'sueldo_diario_integrado', 'sueldo_por_horas',
            'sueldo_cotizacion_base', 'tipo_de_baja',
        ])
        incidence_type_map = {
            'Cambio salario': 'salary_change',
            'Reingreso': 'reentry',
            'Baja': 'leave',
            'Cambio reg. patronal': 'register_change',
        }
        Incidence = self.env['rail.imss.incidence'].sudo().with_context(
            rail_skip_imss_auto_incidence=True,
            tracking_disable=True,
        )
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        stats = {'created': 0, 'existing': 0, 'skipped': 0}
        for row in rows:
            existing = Incidence.search([
                ('rail_legacy_source_model', '=', 'incidencias.nomina'),
                ('rail_legacy_source_id', '=', row['id']),
            ], limit=1)
            if existing:
                stats['existing'] += 1
                continue
            employee = Employee.browse(row.get('employee_id')).exists()
            event_date = row.get('fecha')
            event_type = incidence_type_map.get(row.get('tipo_de_incidencia'))
            if not employee or not event_date or not event_type:
                stats['skipped'] += 1
                continue
            version = employee._get_version(event_date)
            if not version:
                stats['skipped'] += 1
                continue
            equivalent = Incidence.search([
                ('employee_id', '=', employee.id),
                ('version_id', '=', version.id),
                ('incidence_type', '=', event_type),
                ('date', '=', event_date),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if equivalent:
                if not equivalent.rail_legacy_source_model:
                    equivalent.write({
                        'rail_legacy_source_model': 'incidencias.nomina',
                        'rail_legacy_source_id': row['id'],
                    })
                stats['existing'] += 1
                continue
            note_parts = [
                'Migrada desde incidencias.nomina ID %s.' % row['id'],
                'Registro patronal legacy: %s' % (row.get('registro_patronal') or ''),
                'Tipo de baja legacy: %s' % (row.get('tipo_de_baja') or ''),
                'Sueldo diario legacy: %s' % (row.get('sueldo_diario') or 0.0),
                'SDI legacy: %s' % (row.get('sueldo_diario_integrado') or 0.0),
                'Sueldo por hora legacy: %s' % (row.get('sueldo_por_horas') or 0.0),
            ]
            Incidence.create({
                'name': row.get('name') or 'Migración %s' % row['id'],
                'employee_id': employee.id,
                'version_id': version.id,
                'date': event_date,
                'incidence_type': event_type,
                'origin': 'migration',
                'automatic': False,
                'wage_changed': event_type == 'salary_change',
                'sbc_changed': bool(row.get('sueldo_cotizacion_base')),
                'state': row.get('state') if row.get('state') in ('draft', 'done', 'cancel') else 'draft',
                'new_wage': row.get('sueldo_mensual') or 0.0,
                'new_sbc': row.get('sueldo_cotizacion_base') or 0.0,
                'note': '\n'.join(note_parts),
                'rail_legacy_source_model': 'incidencias.nomina',
                'rail_legacy_source_id': row['id'],
            })
            stats['created'] += 1
        return stats

    @api.model
    def _migrate_vacation_balances(self):
        if not self._table_exists('tablas_vacaciones_line') or 'rail.vacation.line' not in self.env.registry:
            return {'created': 0, 'existing': 0, 'skipped': 0}
        rows = self._fetch_dict_rows('tablas_vacaciones_line', ['id', 'form_id', 'dias', 'ano'])
        VacationLine = self.env['rail.vacation.line'].sudo()
        Version = self.env['hr.version'].sudo().with_context(active_test=False)
        stats = {'created': 0, 'existing': 0, 'skipped': 0}
        for row in rows:
            version = Version.browse(row.get('form_id')).exists()
            year = str(row.get('ano') or '')
            if not version or not year:
                stats['skipped'] += 1
                continue
            existing = VacationLine.search([
                ('version_id', '=', version.id),
                ('year', '=', year),
            ], limit=1)
            if existing:
                stats['existing'] += 1
                continue
            first_date = version.employee_id._get_first_contract_date(no_gap=False)
            VacationLine.create({
                'version_id': version.id,
                'year': year,
                'seniority_start_date': first_date,
                'seniority_years': max(int(year) - first_date.year, 0) if first_date and year.isdigit() else 0,
                # El origen v16 solo conserva año y saldo, no el aniversario
                # exacto que generó la bolsa. No se inventa esa fecha.
                'anniversary_date': False,
                'origin': 'migration',
                'state': 'active',
                'granted_days': max(float(row.get('dias') or 0.0), 0.0),
                'used_days': 0.0,
                'note': 'Saldo restante migrado desde tablas.vacaciones.line ID %s.' % row['id'],
            })
            stats['created'] += 1
        return stats
