# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    rail_first_name = fields.Char(
        string='Nombre(s)',
        groups='hr.group_hr_user',
        tracking=True,
        help='Nombre(s) separado(s) conservado(s) desde la nómina v18 para layouts SUA/IDSE/bancos.',
    )
    rail_paternal_surname = fields.Char(
        string='Apellido paterno',
        groups='hr.group_hr_user',
        tracking=True,
        help='Apellido paterno conservado desde la nómina v18 para layouts SUA/IDSE/bancos.',
    )
    rail_maternal_surname = fields.Char(
        string='Apellido materno',
        groups='hr.group_hr_user',
        tracking=True,
        help='Apellido materno conservado desde la nómina v18 para layouts SUA/IDSE/bancos.',
    )


    rail_other_entry_ids = fields.One2many(
        'rail.payroll.other.entry',
        'employee_id',
        string='Otras entradas',
        groups='hr_payroll.group_hr_payroll_user',
        copy=False,
        help='Montos o porcentajes recurrentes del empleado que pueden ser consumidos por reglas salariales MX.',
    )

    # Compatibilidad de lectura con registros creados por la primera versión.
    tabla_otras_entradas = fields.One2many(
        'otras.entradas.empleados',
        'form_id',
        string='Otras entradas (legacy)',
        groups='hr_payroll.group_hr_payroll_manager',
        copy=False,
    )

    def rail_get_other_entry_lines(self, code, active_only=True):
        self.ensure_one()
        lines = self.rail_other_entry_ids.filtered(lambda line: line.code == code)
        if active_only:
            lines = lines.filtered('active')
        return lines

    def rail_get_other_entry_amount(self, code):
        self.ensure_one()
        amount = sum(self.rail_get_other_entry_lines(code).mapped('amount'))
        legacy_lines = self.sudo().tabla_otras_entradas.filtered(
            lambda line: line.codigo == code and line.estado == 'activo'
        )
        return amount + sum(legacy_lines.mapped('monto'))

    def rail_get_other_entry_percentage(self, code):
        self.ensure_one()
        percentage = sum(self.rail_get_other_entry_lines(code).mapped('percentage'))
        legacy_lines = self.sudo().tabla_otras_entradas.filtered(
            lambda line: line.codigo == code and line.estado == 'activo'
        )
        return percentage + sum(legacy_lines.mapped('porcentaje'))

    def rail_get_split_legal_name(self):
        """Return the name parts required by Mexican legacy layouts.

        This helper intentionally does not try to split employee.name automatically.
        In v18 these were explicit fields, and the migration must preserve that
        behavior to avoid generating incorrect SUA/IDSE/bank layouts.
        """
        self.ensure_one()
        return {
            'first_name': self.rail_first_name or '',
            'paternal_surname': self.rail_paternal_surname or '',
            'maternal_surname': self.rail_maternal_surname or '',
        }
