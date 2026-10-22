# -*- coding: utf-8 -*-

import base64
import io

import xlsxwriter

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError


class ProfitSharingWizard(models.TransientModel):
    _name = 'repart.outilidades.wizard'
    _description = 'Reparto de utilidades'

    ano = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.context_today(self).year - 1)
    total_repartir = fields.Float('Monto a repartir', required=True)
    date_slip = fields.Date(string='Fecha de nómina', default=fields.Date.context_today)
    structure_id = fields.Many2one(
        'hr.payroll.structure',
        string='Estructura PTU',
        domain="[('country_id.code', '=', 'MX')]",
        help='La estructura estándar PTU MX se instala con este módulo y se precarga automáticamente.',
    )
    file_data = fields.Binary('Archivo XLSX', readonly=True)
    file_name = fields.Char(readonly=True)
    line_ids = fields.One2many('rail.ptu.preview.line', 'wizard_id', string='Detalle PTU', readonly=True)
    total_nomina = fields.Float('Monto total base', readonly=True)
    total_dias = fields.Float('Días totales', readonly=True)
    coef_monto = fields.Float('Coeficiente monto', readonly=True, digits=(16, 8))
    coef_dias = fields.Float('Coeficiente días', readonly=True, digits=(16, 8))
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('processed', 'Procesado'),
    ], default='draft')
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Procesamiento generado', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if 'structure_id' in fields_list:
            structure = self.env.ref('rail_l10n_mx_payroll_extras.structure_ptu', raise_if_not_found=False)
            if structure:
                values['structure_id'] = structure.id
        return values

    def _reopen_action(self):
        self.ensure_one()
        action = self.env.ref('rail_l10n_mx_payroll_extras.reparto_utilidades_wizard_action').read()[0]
        action['res_id'] = self.id
        return action

    def _get_year_payslips(self):
        self.ensure_one()
        if self.ano < 2000 or self.ano > 9999:
            raise UserError(_('Capture un año válido.'))
        date_from = fields.Date.to_date('%04d-01-01' % self.ano)
        date_to = fields.Date.to_date('%04d-12-31' % self.ano)
        return self.env['hr.payslip'].search([
            ('state', 'in', ('validated', 'paid')),
            ('date_from', '>=', date_from),
            ('date_from', '<=', date_to),
            ('company_id', '=', self.env.company.id),
        ])

    def _eligible_payslips(self):
        payslips = self._get_year_payslips()
        # Equivalencia del filtro legacy employee.regimen == '02': en v19 el régimen está versionado.
        return payslips.filtered(lambda slip: slip.version_id and slip.version_id.l10n_mx_regime_type == '02')

    def _regular_payslips(self, payslips):
        return payslips.filtered(lambda slip: not slip.struct_id.l10n_mx_payroll_type or slip.struct_id.l10n_mx_payroll_type == 'O')

    def _employee_daily_wage(self, employee):
        self.ensure_one()
        reference_date = fields.Date.to_date('%04d-12-31' % self.ano)
        version = employee._get_version(reference_date)
        if not version:
            version = self.env['hr.version'].search([
                ('employee_id', '=', employee.id),
                ('date_version', '<=', reference_date),
            ], order='date_version desc, id desc', limit=1)
        if not version:
            return 0.0
        details = version._rail_get_sbc_calculation_details(reference_date=reference_date)
        return details.get('daily_wage', 0.0)

    def _calculate(self):
        self.ensure_one()
        if self.total_repartir <= 0:
            raise UserError(_('El monto a repartir debe ser mayor a cero.'))

        payslips = self._eligible_payslips()
        regular_payslips = self._regular_payslips(payslips)
        net_lines = payslips.line_ids.filtered(lambda line: line.code == 'NET')
        work_lines = regular_payslips.worked_days_line_ids.filtered(
            lambda line: line.code in ('WORK100', 'VAC', 'FJC', 'SEPT')
        )

        total_amount = sum(net_lines.mapped('total'))
        total_days = sum(work_lines.mapped('number_of_days'))
        if not total_amount:
            raise UserError(_('No hay monto pagado en las nóminas del año seleccionado para trabajadores con régimen 02.'))
        if not total_days:
            raise UserError(_('No hay días laborados en las nóminas del año seleccionado para trabajadores con régimen 02.'))

        coef_days = (self.total_repartir / 2.0) / total_days
        coef_amount = (self.total_repartir / 2.0) / total_amount

        employee_amount = {}
        for line in net_lines:
            employee_amount[line.slip_id.employee_id] = employee_amount.get(line.slip_id.employee_id, 0.0) + line.total
        employee_days = {}
        for line in work_lines:
            employee_days[line.payslip_id.employee_id] = employee_days.get(line.payslip_id.employee_id, 0.0) + line.number_of_days

        commands = [Command.clear()]
        for employee, accumulated in sorted(employee_amount.items(), key=lambda item: item[0].display_name or ''):
            days = employee_days.get(employee, 0.0)
            if not days:
                continue
            ptu_salary = accumulated * coef_amount
            ptu_days = days * coef_days
            raw_total = ptu_salary + ptu_days
            daily_wage = self._employee_daily_wage(employee)
            max_limit = daily_wage * 90.0 if daily_wage else 0.0
            total = min(raw_total, max_limit) if max_limit else raw_total
            commands.append(Command.create({
                'employee_id': employee.id,
                'salary_accumulated': accumulated,
                'days_accumulated': days,
                'ptu_salary': ptu_salary,
                'ptu_days': ptu_days,
                'raw_total': raw_total,
                'daily_wage': daily_wage,
                'max_limit': max_limit,
                'total': total,
            }))

        self.write({
            'line_ids': commands,
            'total_nomina': total_amount,
            'total_dias': total_days,
            'coef_monto': coef_amount,
            'coef_dias': coef_days,
            'state': 'calculated',
        })
        return self.line_ids

    def action_calculate(self):
        self._calculate()
        return self._reopen_action()

    def reparto_utilidades_data(self):
        self.ensure_one()
        lines = self._calculate()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Reparto de utilidades')
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        sheet.write(0, 0, 'Reparto de utilidades', bold)
        sheet.write(1, 0, 'Año', bold)
        sheet.write(1, 1, self.ano)
        sheet.write(2, 0, 'Monto a repartir', bold)
        sheet.write_number(2, 1, self.total_repartir, money)
        sheet.write(3, 0, 'Monto total base', bold)
        sheet.write_number(3, 1, self.total_nomina, money)
        sheet.write(4, 0, 'Días totales', bold)
        sheet.write_number(4, 1, self.total_dias)
        sheet.write(5, 0, 'Coeficiente monto', bold)
        sheet.write_number(5, 1, self.coef_monto)
        sheet.write(6, 0, 'Coeficiente días', bold)
        sheet.write_number(6, 1, self.coef_dias)

        headers = [
            'Empleado', 'Salario acumulado', 'Días acumulados', 'PTU salario', 'PTU días',
            'PTU antes de tope', 'Salario diario', 'Tope 90 días', 'PTU total',
        ]
        for col, header in enumerate(headers):
            sheet.write(8, col, header, bold)
        for row, line in enumerate(lines, start=9):
            sheet.write(row, 0, line.employee_id.display_name)
            for col, value in enumerate([
                line.salary_accumulated, line.days_accumulated, line.ptu_salary, line.ptu_days,
                line.raw_total, line.daily_wage, line.max_limit, line.total,
            ], start=1):
                sheet.write_number(row, col, value, money if col != 2 else None)
        sheet.set_column(0, 0, 32)
        sheet.set_column(1, 8, 18)
        workbook.close()
        output.seek(0)
        filename = 'Reparto_utilidades_%s.xlsx' % self.ano
        self.write({
            'file_data': base64.b64encode(output.read()),
            'file_name': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true' % (self._name, self.id),
            'target': 'self',
        }

    def _validate_ptu_structure(self):
        self.ensure_one()
        structure = self.structure_id
        if not structure:
            raise UserError(_('Seleccione la estructura salarial PTU.'))
        input_type = self.env.ref('rail_l10n_mx_payroll_extras.input_type_ptu')
        consumes_input = structure.rule_ids.filtered(
            lambda rule: (
                rule.amount_other_input_id == input_type
                or rule.condition_other_input_id == input_type
                or "inputs['PTU']" in (rule.amount_python_compute or '')
                or 'inputs["PTU"]' in (rule.amount_python_compute or '')
            )
        )
        if not consumes_input:
            raise UserError(_(
                'La estructura %(structure)s no contiene una regla que consuma la entrada PTU. '
                'Configure la regla fiscal de PTU antes de generar los recibos.',
                structure=structure.display_name,
            ))
        return structure, input_type

    def reparto_utilidades_payslip(self):
        self.ensure_one()
        if not self.date_slip:
            raise UserError(_('Falta colocar una fecha para la nómina.'))
        lines = self.line_ids if self.state == 'calculated' and self.line_ids else self._calculate()
        structure, input_type = self._validate_ptu_structure()

        run = self.env['hr.payslip.run'].create({
            'name': _('Reparto Utilidades %s') % self.ano,
            'date_start': self.date_slip,
            'date_end': self.date_slip,
            'structure_id': structure.id,
            'company_id': self.env.company.id,
            'schedule_pay': structure.type_id.default_schedule_pay,
        })
        generated = self.env['hr.payslip']
        for line in lines:
            employee = line.employee_id
            version = employee._get_version(self.date_slip)
            if not version:
                raise UserError(_(
                    'No se encontró una versión laboral vigente para %(employee)s en %(date)s.',
                    employee=employee.display_name,
                    date=self.date_slip,
                ))
            slip = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'version_id': version.id,
                'date_from': self.date_slip,
                'date_to': self.date_slip,
                'name': _('PTU %s - %s') % (self.ano, employee.display_name),
                'struct_id': structure.id,
                'payslip_run_id': run.id,
                'rail_apply_installments': False,
                'input_line_ids': [Command.create({
                    'name': _('Reparto utilidades'),
                    'input_type_id': input_type.id,
                    'amount': line.total,
                })],
            })
            slip.compute_sheet()
            generated |= slip

        self.write({'payslip_run_id': run.id, 'state': 'processed'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recibos PTU %s') % self.ano,
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated.ids)],
            'context': {'search_default_payslip_run_id': run.id},
        }


class ProfitSharingPreviewLine(models.TransientModel):
    _name = 'rail.ptu.preview.line'
    _description = 'Detalle cálculo PTU'
    _order = 'employee_id'

    wizard_id = fields.Many2one('repart.outilidades.wizard', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    salary_accumulated = fields.Float('Salario acumulado')
    days_accumulated = fields.Float('Días acumulados')
    ptu_salary = fields.Float('PTU salario')
    ptu_days = fields.Float('PTU días')
    raw_total = fields.Float('PTU antes de tope')
    daily_wage = fields.Float('Salario diario')
    max_limit = fields.Float('Tope 90 días')
    total = fields.Float('PTU total')
