# -*- coding: utf-8 -*-

import base64
import io

import xlsxwriter

from odoo import fields, models, _
from odoo.exceptions import UserError


class WizardSbcBimestral(models.TransientModel):
    _name = 'wizard.sbc.bimestral'
    _description = 'Cálculo SBC bimestral'

    primer_fecha_inicio = fields.Date('Inicio primer mes', required=True)
    primer_fecha_fin = fields.Date('Fin primer mes', required=True)
    segundo_fecha_inicio = fields.Date('Inicio segundo mes', required=True)
    segundo_fecha_fin = fields.Date('Fin segundo mes', required=True)
    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    detalles = fields.Boolean('Incluir detalle por regla')
    effective_date = fields.Date('Fecha efectiva cambio SBC', required=True, default=fields.Date.context_today)
    line_ids = fields.One2many('wizard.sbc.bimestral.line', 'wizard_id', string='Resultados')
    file_content = fields.Binary('Archivo XLSX', readonly=True)
    file_name = fields.Char('Nombre archivo', readonly=True)

    def action_compute(self):
        self.ensure_one()
        self._validate_dates()
        self.line_ids.unlink()
        lines = []
        for employee in self._get_employees():
            result = self._compute_employee_sbc(employee)
            if result:
                lines.append((0, 0, result))
        self.write({'line_ids': lines})
        return self._reopen()

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_compute()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('SBC Bimestral')
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.0000'})
        headers = [
            'No. empleado', 'Empleado', 'NSS', 'Registro patronal', 'Fecha alta', 'Departamento',
            'Sueldo diario', 'Factor integración', 'Días periodo', 'SBC base calculado',
            'SBC vigente anterior', 'Variable gravada', 'Variable diaria', 'SBC nuevo',
            'Versión', 'Estado',
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)
        row = 1
        for line in self.line_ids:
            worksheet.write(row, 0, line.registration_number or '')
            worksheet.write(row, 1, line.employee_id.display_name or '')
            worksheet.write(row, 2, line.ssnid or '')
            worksheet.write(row, 3, line.imss_registration or '')
            worksheet.write(row, 4, str(line.contract_date_start or ''))
            worksheet.write(row, 5, line.department_id.display_name or '')
            worksheet.write_number(row, 6, line.daily_wage or 0.0, money)
            worksheet.write_number(row, 7, line.integration_factor or 0.0)
            worksheet.write_number(row, 8, line.period_days or 0.0)
            worksheet.write_number(row, 9, line.fixed_sbc or 0.0, money)
            worksheet.write_number(row, 10, line.previous_sbc or 0.0, money)
            worksheet.write_number(row, 11, line.variable_taxable_amount or 0.0, money)
            worksheet.write_number(row, 12, line.variable_daily_amount or 0.0, money)
            worksheet.write_number(row, 13, line.new_sbc or 0.0, money)
            worksheet.write(row, 14, line.version_id.display_name or '')
            worksheet.write(row, 15, dict(line._fields['state'].selection).get(line.state, line.state))
            row += 1
        worksheet.autofilter(0, 0, max(row - 1, 1), len(headers) - 1)
        for col in range(len(headers)):
            worksheet.set_column(col, col, 18)
        workbook.close()
        self.write({
            'file_content': base64.b64encode(output.getvalue()),
            'file_name': 'SBC_Bimestral_%s_%s.xlsx' % (self.primer_fecha_inicio, self.segundo_fecha_fin),
        })
        return self._reopen()

    def action_apply_new_sbc(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Debe calcular el SBC antes de aplicarlo.'))
        for line in self.line_ids.filtered(lambda item: item.state == 'draft'):
            line.action_apply_new_sbc()
        return self._reopen()

    def _validate_dates(self):
        if self.primer_fecha_inicio > self.primer_fecha_fin:
            raise UserError(_('El rango del primer mes no es válido.'))
        if self.segundo_fecha_inicio > self.segundo_fecha_fin:
            raise UserError(_('El rango del segundo mes no es válido.'))
        if self.primer_fecha_fin >= self.segundo_fecha_inicio:
            raise UserError(_('El segundo mes debe iniciar después del primer mes.'))

    def _get_employees(self):
        if self.employee_ids:
            return self.employee_ids
        return self.env['hr.employee'].search([('company_id', '=', self.env.company.id)])

    def _compute_employee_sbc(self, employee):
        version = employee._get_version(self.segundo_fecha_fin)
        if not version:
            return False
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', self.primer_fecha_inicio),
            ('date_to', '<=', self.segundo_fecha_fin),
            ('state', 'in', ['validated', 'paid']),
        ])
        period_days = self._get_period_worked_days(payslips) or 1.0

        sbc_details = version._rail_get_sbc_calculation_details(
            reference_date=self.effective_date,
            raise_if_not_found=True,
        )
        base_sbc = sbc_details['sbc']
        variable_total = self._get_variable_taxable_amount(
            payslips, version, period_days, base_sbc
        )
        variable_daily = variable_total / period_days
        max_sbc = sbc_details['max_sbc']
        new_sbc = base_sbc + variable_daily
        if max_sbc:
            new_sbc = min(new_sbc, max_sbc)

        return {
            'employee_id': employee.id,
            'version_id': version.id,
            'registration_number': employee.registration_number or '',
            'ssnid': version.ssnid or employee.ssnid or '',
            'imss_registration': employee.company_id.l10n_mx_imss_id or '',
            'contract_date_start': sbc_details['first_contract_date'] or version.contract_date_start,
            'department_id': version.department_id.id,
            'daily_wage': sbc_details['daily_wage'],
            'integration_factor': sbc_details['integration_factor'],
            'period_days': period_days,
            'fixed_sbc': base_sbc,
            'previous_sbc': version.rail_fixed_sbc,
            'variable_taxable_amount': variable_total,
            'variable_daily_amount': variable_daily,
            'new_sbc': round(new_sbc, 4),
            'state': 'draft',
        }

    def _get_period_worked_days(self, payslips):
        accepted_codes = {'WORK100', 'FJC', 'P025', 'VAC', 'SEPT'}
        total = 0.0
        for payslip in payslips:
            for worked_day in payslip.worked_days_line_ids:
                if worked_day.code in accepted_codes or worked_day.is_paid:
                    total += worked_day.number_of_days or 0.0
        return total

    def _get_variable_taxable_amount(self, payslips, version, period_days, base_sbc):
        total = 0.0
        for line in payslips.mapped('line_ids').filtered(
            lambda item: item.salary_rule_id.rail_sbc_variable
        ):
            total += self._get_taxable_line_amount(line, version, period_days, base_sbc)
        return total

    def _get_taxable_line_amount(self, line, version, period_days, base_sbc):
        rule = line.salary_rule_id
        amount = line.total or 0.0
        if rule.rail_sbc_variable_type == 'all':
            return amount
        if rule.rail_sbc_variable_type == 'excess_uma':
            uma = self._get_rule_parameter(
                'l10n_mx_uma', line.slip_id.date_to, raise_if_not_found=False
            ) or {}
            daily_uma = uma.get('daily', 0.0) if isinstance(uma, dict) else float(uma or 0.0)
            exempt = daily_uma * period_days * (rule.rail_sbc_variable_amount or 0.0) / 100.0
            return max(amount - exempt, 0.0)
        if rule.rail_sbc_variable_type == 'excess_sbc':
            exempt = base_sbc * period_days * (rule.rail_sbc_variable_amount or 0.0) / 100.0
            return max(amount - exempt, 0.0)
        return amount

    def _get_rule_parameter(self, code, reference_date, raise_if_not_found=True):
        return self.env['hr.rule.parameter']._get_parameter_from_code(
            code, reference_date, raise_if_not_found=raise_if_not_found
        )

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class WizardSbcBimestralLine(models.TransientModel):
    _name = 'wizard.sbc.bimestral.line'
    _description = 'Resultado cálculo SBC bimestral'

    wizard_id = fields.Many2one('wizard.sbc.bimestral', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    version_id = fields.Many2one('hr.version', string='Versión laboral', required=True)
    registration_number = fields.Char('No. empleado')
    ssnid = fields.Char('NSS')
    imss_registration = fields.Char('Registro patronal')
    contract_date_start = fields.Date('Fecha alta')
    department_id = fields.Many2one('hr.department', string='Departamento')
    daily_wage = fields.Float('Sueldo diario', digits='Payroll')
    integration_factor = fields.Float('Factor integración', digits='Payroll')
    period_days = fields.Float('Días periodo', digits='Payroll')
    fixed_sbc = fields.Float('SBC base calculado', digits='Payroll')
    previous_sbc = fields.Float('SBC vigente anterior', digits='Payroll')
    variable_taxable_amount = fields.Float('Variable gravada', digits='Payroll')
    variable_daily_amount = fields.Float('Variable diaria', digits='Payroll')
    new_sbc = fields.Float('SBC nuevo', digits='Payroll')
    new_version_id = fields.Many2one('hr.version', string='Nueva versión', readonly=True)
    incidence_id = fields.Many2one('rail.imss.incidence', string='Incidencia IMSS', readonly=True)
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('applied', 'Aplicado'),
        ('error', 'Error'),
    ], default='draft')
    error_message = fields.Text('Error')

    def action_apply_new_sbc(self):
        for line in self:
            if line.state == 'applied':
                continue
            try:
                previous_sbc = line.version_id.rail_fixed_sbc or line.previous_sbc
                values = {
                    'rail_previous_sbc': previous_sbc,
                    'rail_fixed_sbc': line.new_sbc,
                    'rail_sbc_effective_date': line.wizard_id.effective_date,
                }
                imss_context = {
                    'rail_imss_incidence_origin': 'sbc_bimonthly',
                    'rail_imss_force_salary_change': True,
                    'rail_imss_effective_date': line.wizard_id.effective_date,
                    'rail_imss_incidence_note': _('Creado desde cálculo SBC bimestral.'),
                }
                effective_date = line.wizard_id.effective_date
                if line.version_id.date_version == effective_date:
                    new_version = line.version_id.with_context(**imss_context)
                    new_version.write(values)
                else:
                    new_version = line.version_id.with_context(**imss_context).rail_create_new_version(
                        effective_date, values
                    )
                incidence = self.env['rail.imss.incidence'].search([
                    ('employee_id', '=', line.employee_id.id),
                    ('version_id', '=', new_version.id),
                    ('date', '=', effective_date),
                    ('incidence_type', '=', 'salary_change'),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                if not incidence:
                    incidence = self.env['rail.imss.incidence'].rail_get_or_create_event(
                        employee=line.employee_id,
                        version=new_version,
                        event_date=effective_date,
                        incidence_type='salary_change',
                        origin='sbc_bimonthly',
                        values={
                            'old_sbc': previous_sbc,
                            'new_sbc': line.new_sbc,
                            'old_wage': line.version_id.wage,
                            'new_wage': new_version.wage,
                            'sbc_changed': True,
                            'note': _('Creado desde cálculo SBC bimestral.'),
                        },
                        automatic=True,
                    )
                line.write({
                    'new_version_id': new_version.id,
                    'incidence_id': incidence.id,
                    'state': 'applied',
                    'error_message': False,
                })
            except Exception as error:
                line.write({'state': 'error', 'error_message': str(error)})
        return True
