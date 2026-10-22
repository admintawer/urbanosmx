# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    loan_request = fields.Integer(
        string='Solicitudes de préstamo por año',
        default=1,
        required=True,
        groups='hr_payroll.group_hr_payroll_user',
        help='Campo legacy de v18 para limitar préstamos por empleado/año.',
    )
    rail_loan_count = fields.Integer(string='Préstamos', compute='_compute_rail_loan_count')

    def _compute_rail_loan_count(self):
        groups = self.env['employee.loan'].read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'],
            ['employee_id'],
        )
        mapped = {group['employee_id'][0]: group['employee_id_count'] for group in groups if group.get('employee_id')}
        for employee in self:
            employee.rail_loan_count = mapped.get(employee.id, 0)

    def action_rail_open_loans(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('rail_l10n_mx_payroll_extras.action_employee_loan')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action
