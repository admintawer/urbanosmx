# -*- coding: utf-8 -*-

import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    @api.model
    def _rail_configure_legacy_catalog(self):
        """Create/update the legacy Mexican payroll work-entry/time-off catalog.

        The routine intentionally searches by technical code before creating a
        record. This makes it safe to execute on every module upgrade and also
        lets it reuse records manually configured in an existing database.
        """
        mexico = self.env.ref('base.mx')

        work_entry_catalog = [
            {'code': 'DFES', 'name': 'Día festivo', 'is_leave': True, 'color': 4},
            {'code': 'FI', 'name': 'Falta injustificada', 'is_leave': True, 'color': 4},
            {'code': 'FJC', 'name': 'Falta con goce de sueldo', 'is_leave': True, 'color': 0},
            {'code': 'FJS', 'name': 'Falta sin goce de sueldo', 'is_leave': True, 'color': 4},
            {'code': 'FR', 'name': 'Falta por retardo', 'is_leave': True, 'color': 4},
            {
                'code': 'INC_EG',
                'name': 'Incapacidad por enfermedad general',
                'is_leave': True,
                'color': 4,
                'l10n_mx_sat_code': '02',
            },
            {
                'code': 'INC_MAT',
                'name': 'Incapacidad por maternidad',
                'is_leave': True,
                'color': 4,
                'l10n_mx_sat_code': '03',
            },
            {
                'code': 'INC_RT',
                'name': 'Incapacidad por riesgo de trabajo',
                'is_leave': True,
                'color': 4,
                'l10n_mx_sat_code': '01',
            },
            {'code': 'SEPT', 'name': 'Séptimo día', 'is_leave': False, 'color': 0},
            {'code': 'VAC', 'name': 'Vacaciones', 'is_leave': True, 'color': 4},
        ]

        work_entry_by_code = {}
        for item in work_entry_catalog:
            code = item['code']
            work_entry_type = self.search([
                ('code', '=', code),
                ('country_id', 'in', [False, mexico.id]),
            ], limit=1)

            values = {
                'name': item['name'],
                'active': True,
                'is_leave': item['is_leave'],
                'color': item['color'],
            }
            if 'l10n_mx_sat_code' in self._fields and item.get('l10n_mx_sat_code'):
                values['l10n_mx_sat_code'] = item['l10n_mx_sat_code']

            if work_entry_type:
                # Do not force country_id on an existing record: Odoo prevents
                # changing it once work entries already use the type.
                work_entry_type.write(values)
            else:
                values.update({
                    'code': code,
                    'country_id': mexico.id,
                })
                work_entry_type = self.create(values)
            work_entry_by_code[code] = work_entry_type

        # WORK100 is native. Keep its native identity and only ensure it is
        # active; never recreate or change its technical code.
        attendance = self.search([('code', '=', 'WORK100')], limit=1)
        if attendance and not attendance.active:
            attendance.active = True

        leave_type_catalog = [
            {'code': 'DFES', 'name': 'Día festivo'},
            {'code': 'FI', 'name': 'Falta injustificada', 'unpaid': True},
            {'code': 'FJC', 'name': 'Falta con goce de sueldo'},
            {'code': 'FJS', 'name': 'Falta sin goce de sueldo', 'unpaid': True},
            {'code': 'FR', 'name': 'Falta por retardo', 'unpaid': True, 'request_unit': 'hour'},
            {'code': 'INC_EG', 'name': 'Incapacidad por enfermedad general'},
            {'code': 'INC_MAT', 'name': 'Incapacidad por maternidad'},
            {'code': 'INC_RT', 'name': 'Incapacidad por riesgo de trabajo'},
            {'code': 'VAC', 'name': 'Vacaciones', 'rail_is_vacation': True},
        ]

        LeaveType = self.env['hr.leave.type'].sudo().with_context(active_test=False)
        for item in leave_type_catalog:
            code = item['code']
            leave_type = LeaveType.search([
                ('code', '=', code),
                ('company_id', 'in', [False] + self.env.companies.ids),
            ], limit=1)
            structural_values = {
                'requires_allocation': False,
                'employee_requests': True,
                'leave_validation_type': 'hr',
                'request_unit': item.get('request_unit', 'day'),
                'unpaid': item.get('unpaid', False),
            }
            catalog_values = {
                'name': item['name'],
                'active': True,
                'work_entry_type_id': work_entry_by_code[code].id,
            }
            if 'rail_is_vacation' in LeaveType._fields:
                catalog_values['rail_is_vacation'] = item.get('rail_is_vacation', False)

            if leave_type:
                # Odoo 19 prevents changing requires_allocation after a type
                # has already been used in hr.leave. Preserve all structural
                # settings on used types and only synchronize safe catalog
                # metadata. This also avoids changing historical payroll/time
                # off behavior during a module upgrade.
                has_leaves = bool(self.env['hr.leave'].sudo().search_count([
                    ('holiday_status_id', '=', leave_type.id),
                ], limit=1))
                values_to_write = dict(catalog_values)
                if not has_leaves:
                    values_to_write.update(structural_values)
                else:
                    _logger.info(
                        'Legacy time-off type %s (%s) already has leave records; '
                        'preserving allocation, validation, duration and unpaid settings.',
                        leave_type.display_name,
                        code,
                    )
                leave_type.write(values_to_write)
            else:
                create_values = dict(catalog_values)
                create_values.update(structural_values)
                create_values.update({
                    'code': code,
                    'company_id': self.env.company.id,
                })
                LeaveType.create(create_values)

        return True
