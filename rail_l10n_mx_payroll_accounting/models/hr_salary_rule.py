# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RailPayrollAccountMapping(models.Model):
    _name = 'rail.payroll.account.mapping'
    _description = 'Cuenta contable especial de nómina'
    _order = 'sequence, id'
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Regla salarial',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help='Las reglas salariales de Odoo 19 no tienen company_id. La compañía se define explícitamente en cada mapeo.',
    )
    side = fields.Selection([
        ('debit', 'Débito'),
        ('credit', 'Crédito'),
    ], string='Lado', required=True, default='debit')
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        index=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        index=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    account_id = fields.Many2one(
        'account.account',
        string='Cuenta contable',
        required=True,
        check_company=True,
    )
    analytic_distribution = fields.Json(
        string='Distribución analítica',
        groups='analytic.group_analytic_accounting',
        help='Si se define, reemplaza la analítica de la regla/versión para esta cuenta especial.',
    )
    active = fields.Boolean(default=True)

    @api.constrains('employee_id', 'department_id', 'company_id')
    def _check_scope(self):
        for record in self:
            if record.employee_id and record.department_id:
                raise ValidationError(_('Defina empleado o departamento, no ambos, en una misma cuenta especial.'))
            if not record.employee_id and not record.department_id:
                raise ValidationError(_('Debe definir un empleado o un departamento para la cuenta especial.'))
            if record.employee_id and record.employee_id.company_id != record.company_id:
                raise ValidationError(_('El empleado debe pertenecer a la compañía del mapeo contable.'))
            if record.department_id.company_id and record.department_id.company_id != record.company_id:
                raise ValidationError(_('El departamento debe pertenecer a la compañía del mapeo contable.'))


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    rail_account_mapping_ids = fields.One2many(
        'rail.payroll.account.mapping',
        'salary_rule_id',
        string='Cuentas especiales por empleado/departamento',
        help='Migración funcional de nomina.deudora/nomina.acreedora de v18. Tiene prioridad sobre las cuentas estándar de la regla.',
    )

    def rail_get_special_account_mapping(self, side, payslip):
        self.ensure_one()
        employee = payslip.employee_id
        department = payslip.version_id.department_id or employee.department_id
        mappings = self.rail_account_mapping_ids.filtered(
            lambda mapping: (
                mapping.active
                and mapping.side == side
                and mapping.company_id == payslip.company_id
            )
        )
        employee_mapping = mappings.filtered(lambda mapping: mapping.employee_id == employee)[:1]
        if employee_mapping:
            return employee_mapping
        if department:
            department_mapping = mappings.filtered(lambda mapping: mapping.department_id == department)[:1]
            if department_mapping:
                return department_mapping
        return self.env['rail.payroll.account.mapping']
