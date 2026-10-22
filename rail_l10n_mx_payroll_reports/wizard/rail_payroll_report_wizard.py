# -*- coding: utf-8 -*-

import base64
import io
from collections import defaultdict
from datetime import date

from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except Exception:  # pragma: no cover
    xlsxwriter = None


class RailPayrollReportWizard(models.TransientModel):
    _name = 'rail.payroll.report.wizard'
    _description = 'Rail Mexican Payroll Report Wizard'

    report_type = fields.Selection([
        ('employee', 'Total por empleado'),
        ('department', 'Total por departamento'),
        ('rules', 'Detalle por reglas salariales'),
        ('isr_annual', 'Cálculo ISR anual'),
        ('isn', 'Reporte ISN'),
        ('imss', 'Reporte IMSS'),
        ('savings_fund', 'Caja / fondo de ahorro'),
        ('movements', 'Altas y bajas IMSS'),
        ('liquidations', 'Liquidaciones'),
        ('ptu', 'PTU / Reparto de utilidades'),
    ], string='Reporte', required=True, default=lambda self: self.env.context.get('default_report_type') or 'employee')

    date_from = fields.Date('Fecha inicial', required=True, default=lambda self: date.today().replace(month=1, day=1))
    date_to = fields.Date('Fecha final', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Procesamiento de nómina', domain="[('company_id', '=', company_id)]")
    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    department_ids = fields.Many2many('hr.department', string='Departamentos')
    state_filter = fields.Selection([
        ('validated_paid', 'Validadas y pagadas'),
        ('validated', 'Solo validadas'),
        ('paid', 'Solo pagadas'),
        ('draft', 'Borrador'),
        ('all', 'Todas excepto canceladas'),
    ], string='Estado de recibos', default='validated_paid', required=True)
    rule_codes = fields.Char('Códigos de reglas', help='Lista separada por comas. Si se deja vacío se usan los códigos estándar del reporte seleccionado.')
    include_cancelled_movements = fields.Boolean('Incluir incidencias canceladas')
    isn_rate = fields.Float('Tasa ISN %', default=3.0)
    file_data = fields.Binary('Archivo', readonly=True)
    file_name = fields.Char('Nombre del archivo', readonly=True)
    message = fields.Text('Resultado', readonly=True)

    def action_generate_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_('La librería xlsxwriter no está instalada en el entorno.'))
        if self.date_from > self.date_to:
            raise UserError(_('La fecha inicial no puede ser mayor que la fecha final.'))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        formats = self._get_formats(workbook)
        dispatch = {
            'employee': self._sheet_employee_totals,
            'department': self._sheet_department_totals,
            'rules': self._sheet_rule_pivot,
            'isr_annual': self._sheet_isr_annual,
            'isn': self._sheet_isn,
            'imss': self._sheet_imss,
            'savings_fund': self._sheet_savings_fund,
            'movements': self._sheet_movements,
            'liquidations': self._sheet_liquidations,
            'ptu': self._sheet_ptu,
        }
        dispatch[self.report_type](workbook, formats)
        workbook.close()
        output.seek(0)
        filename = 'reporte_nomina_%s_%s_%s.xlsx' % (self.report_type, self.date_from, self.date_to)
        self.write({
            'file_data': base64.b64encode(output.read()),
            'file_name': filename,
            'message': _('Reporte generado correctamente: %s') % filename,
        })
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'view_mode': 'form', 'res_id': self.id, 'target': 'new'}

    def action_download(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Primero genera el archivo.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=file_data&download=true&filename=%s' % (self._name, self.id, self.file_name or 'reporte_nomina.xlsx'),
            'target': 'self',
        }

    def _get_formats(self, workbook):
        return {
            'title': workbook.add_format({'bold': True, 'font_size': 14}),
            'header': workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#D9EAF7'}),
            'date': workbook.add_format({'num_format': 'yyyy-mm-dd'}),
            'money': workbook.add_format({'num_format': '#,##0.00'}),
            'percent': workbook.add_format({'num_format': '0.00%'}),
            'text': workbook.add_format({}),
            'bold': workbook.add_format({'bold': True}),
        }

    def _write_title(self, ws, title, formats, last_col=8):
        ws.merge_range(0, 0, 0, last_col, title, formats['title'])
        ws.write(1, 0, _('Compañía'), formats['bold']); ws.write(1, 1, self.company_id.display_name)
        ws.write(2, 0, _('Periodo'), formats['bold']); ws.write(2, 1, '%s - %s' % (self.date_from, self.date_to))
        if self.payslip_run_id:
            ws.write(3, 0, _('Procesamiento'), formats['bold']); ws.write(3, 1, self.payslip_run_id.display_name)

    def _write_headers(self, ws, row, headers, formats):
        for col, header in enumerate(headers):
            ws.write(row, col, header, formats['header'])
        ws.freeze_panes(row + 1, 0)
        ws.autofilter(row, 0, row, len(headers) - 1)

    def _get_payslip_domain(self):
        domain = [('company_id', '=', self.company_id.id), ('date_from', '>=', self.date_from), ('date_to', '<=', self.date_to), ('state', '!=', 'cancel')]
        if self.payslip_run_id:
            domain.append(('payslip_run_id', '=', self.payslip_run_id.id))
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        if self.state_filter == 'validated_paid':
            domain.append(('state', 'in', ['validated', 'paid']))
        elif self.state_filter in ('validated', 'paid', 'draft'):
            domain.append(('state', '=', self.state_filter))
        return domain

    def _get_payslips(self):
        payslips = self.env['hr.payslip'].search(self._get_payslip_domain(), order='employee_id, date_from, date_to')
        if not payslips:
            raise UserError(_('No se encontraron recibos para los filtros seleccionados.'))
        return payslips

    def _parse_codes(self, default_codes=None):
        raw = self.rule_codes or ''
        codes = [code.strip().upper() for code in raw.replace('\n', ',').split(',') if code.strip()]
        return codes or list(default_codes or [])

    def _line_total(self, slip, codes):
        code_set = set(codes)
        return sum(line.total for line in slip.line_ids if (line.code or '').upper() in code_set)

    def _line_total_contains(self, slip, tokens):
        token_set = [token.upper() for token in tokens]
        return sum(line.total for line in slip.line_ids if any(token in (line.code or '').upper() for token in token_set))

    def _employee_split_name(self, employee):
        if hasattr(employee, 'rail_get_split_legal_name'):
            vals = employee.rail_get_split_legal_name()
            return vals.get('first_name') or '', vals.get('paternal_surname') or '', vals.get('maternal_surname') or ''
        return getattr(employee, 'rail_first_name', '') or employee.name or '', getattr(employee, 'rail_paternal_surname', '') or '', getattr(employee, 'rail_maternal_surname', '') or ''

    def _employee_number(self, employee):
        return employee.registration_number or ''

    def _write_slip_common(self, ws, row, slip, formats):
        first, paternal, maternal = self._employee_split_name(slip.employee_id)
        values = [self._employee_number(slip.employee_id), slip.employee_id.name or '', first, paternal, maternal, slip.department_id.display_name or '', slip.version_id.display_name or '', slip.date_from, slip.date_to, slip.payslip_run_id.display_name or '', slip.struct_id.display_name or '', slip.state]
        for col, value in enumerate(values):
            fmt = formats['date'] if col in (7, 8) else formats['text']
            ws.write(row, col, value, fmt)
        return len(values)

    def _sheet_employee_totals(self, workbook, formats):
        payslips = self._get_payslips(); ws = workbook.add_worksheet('Total por empleado')
        self._write_title(ws, _('Total por empleado'), formats, 15)
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado'), _('Básico'), _('Bruto'), _('Neto'), _('Costo patronal')]
        codes = self._parse_codes(); headers += codes; self._write_headers(ws, 5, headers, formats)
        row = 6; totals = defaultdict(float)
        for slip in payslips:
            col = self._write_slip_common(ws, row, slip, formats)
            for val in [slip.basic_wage, slip.gross_wage, slip.net_wage, slip.employer_cost]:
                ws.write(row, col, val, formats['money']); totals[col] += val; col += 1
            for code in codes:
                val = self._line_total(slip, [code]); ws.write(row, col, val, formats['money']); totals[col] += val; col += 1
            row += 1
        ws.write(row, 0, _('Totales'), formats['bold'])
        for col, total in totals.items(): ws.write(row, col, total, formats['money'])
        ws.set_column(0, len(headers), 16)

    def _sheet_department_totals(self, workbook, formats):
        payslips = self._get_payslips(); grouped = defaultdict(lambda: {'count': 0, 'basic': 0.0, 'gross': 0.0, 'net': 0.0, 'employer': 0.0})
        for slip in payslips:
            key = slip.department_id.display_name or _('Sin departamento'); grouped[key]['count'] += 1; grouped[key]['basic'] += slip.basic_wage; grouped[key]['gross'] += slip.gross_wage; grouped[key]['net'] += slip.net_wage; grouped[key]['employer'] += slip.employer_cost
        ws = workbook.add_worksheet('Total por departamento'); self._write_title(ws, _('Total por departamento'), formats, 6)
        headers = [_('Departamento'), _('Recibos'), _('Básico'), _('Bruto'), _('Neto'), _('Costo patronal')]; self._write_headers(ws, 5, headers, formats)
        row = 6; totals = defaultdict(float)
        for department, vals in sorted(grouped.items()):
            ws.write(row, 0, department); ws.write(row, 1, vals['count'])
            for idx, key in enumerate(['basic', 'gross', 'net', 'employer'], start=2): ws.write(row, idx, vals[key], formats['money']); totals[idx] += vals[key]
            row += 1
        ws.write(row, 0, _('Totales'), formats['bold']); ws.write(row, 1, sum(v['count'] for v in grouped.values()))
        for idx in range(2, 6): ws.write(row, idx, totals[idx], formats['money'])
        ws.set_column(0, 5, 22)

    def _sheet_rule_pivot(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes() or sorted(set(line.code for line in payslips.mapped('line_ids') if line.code))
        ws = workbook.add_worksheet('Reglas salariales'); self._write_title(ws, _('Detalle por reglas salariales'), formats, 12 + len(codes))
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado')] + codes; self._write_headers(ws, 5, headers, formats)
        row = 6; totals = defaultdict(float)
        for slip in payslips:
            col = self._write_slip_common(ws, row, slip, formats)
            for code in codes:
                val = self._line_total(slip, [code]); ws.write(row, col, val, formats['money']); totals[col] += val; col += 1
            row += 1
        ws.write(row, 0, _('Totales'), formats['bold'])
        for col, total in totals.items(): ws.write(row, col, total, formats['money'])
        ws.set_column(0, len(headers), 16)

    def _sheet_isr_annual(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes(['ISR', 'ISR2', 'D060', 'O007', 'SUBSIDY', 'SUBSIDY_CURRENT_MONTH', 'SUBSIDY_NEXT_MONTH'])
        grouped = defaultdict(lambda: defaultdict(float)); employees = {}
        for slip in payslips:
            employees[slip.employee_id.id] = slip.employee_id; grouped[slip.employee_id.id]['gross'] += slip.gross_wage; grouped[slip.employee_id.id]['net'] += slip.net_wage
            for code in codes: grouped[slip.employee_id.id][code] += self._line_total(slip, [code])
        ws = workbook.add_worksheet('ISR anual'); self._write_title(ws, _('Cálculo ISR anual - acumulados por recibo'), formats, 10 + len(codes))
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Bruto'), _('Neto')] + codes; self._write_headers(ws, 5, headers, formats)
        row = 6
        for employee_id, employee in sorted(employees.items(), key=lambda item: item[1].name or ''):
            first, paternal, maternal = self._employee_split_name(employee); vals = grouped[employee_id]
            row_values = [self._employee_number(employee), employee.name, first, paternal, maternal, vals['gross'], vals['net']]
            for col, value in enumerate(row_values): ws.write(row, col, value, formats['money'] if col >= 5 else formats['text'])
            col = len(row_values)
            for code in codes: ws.write(row, col, vals[code], formats['money']); col += 1
            row += 1
        ws.set_column(0, len(headers), 16)

    def _sheet_isn(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes(['GROSS'])
        ws = workbook.add_worksheet('ISN'); self._write_title(ws, _('Reporte ISN'), formats, 16)
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado'), _('Base ISN'), _('Tasa'), _('ISN estimado')]; self._write_headers(ws, 5, headers, formats)
        row = 6; total_base = total_tax = 0.0
        for slip in payslips:
            col = self._write_slip_common(ws, row, slip, formats); base = slip.gross_wage if codes == ['GROSS'] else self._line_total(slip, codes); tax = base * (self.isn_rate / 100.0)
            ws.write(row, col, base, formats['money']); col += 1; ws.write(row, col, self.isn_rate / 100.0, formats['percent']); col += 1; ws.write(row, col, tax, formats['money']); total_base += base; total_tax += tax; row += 1
        ws.write(row, 0, _('Totales'), formats['bold']); ws.write(row, 12, total_base, formats['money']); ws.write(row, 14, total_tax, formats['money']); ws.set_column(0, len(headers), 16)

    def _sheet_imss(self, workbook, formats):
        payslips = self._get_payslips()
        codes = self._parse_codes()
        ws = workbook.add_worksheet('IMSS')
        self._write_title(ws, _('Reporte IMSS'), formats, 17)
        headers = [
            _('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'),
            _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'),
            _('Procesamiento'), _('Estructura'), _('Estado'),
            _('Sueldo base de cotización (IMSS)'),
        ]
        headers += codes or [
            _('IMSS empleado'), _('IMSS patrón'), _('INFONAVIT'),
            _('Total IMSS/INFONAVIT'),
        ]
        self._write_headers(ws, 5, headers, formats)
        row = 6
        totals = defaultdict(float)
        for slip in payslips:
            col = self._write_slip_common(ws, row, slip, formats)
            sbc = slip.version_id.rail_fixed_sbc or 0.0
            ws.write(row, col, sbc, formats['money'])
            col += 1
            values = (
                [self._line_total(slip, [code]) for code in codes]
                if codes
                else [
                    self._line_total_contains(slip, ['IMSS_EMPLOYEE', 'IMSS_EMP']),
                    self._line_total_contains(slip, ['IMSS_EMPLOYER', 'IMSS_PAT', 'PAT_']),
                    self._line_total_contains(slip, ['INFONAVIT']),
                ]
            )
            if not codes:
                values.append(sum(values))
            for value in values:
                ws.write(row, col, value, formats['money'])
                totals[col] += value
                col += 1
            row += 1
        ws.write(row, 0, _('Totales'), formats['bold'])
        for col, total in totals.items():
            ws.write(row, col, total, formats['money'])
        ws.set_column(0, len(headers), 16)

    def _sheet_savings_fund(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes(['CAJA', 'FONDO', 'AHORRO', 'SAVINGS'])
        ws = workbook.add_worksheet('Caja ahorro'); self._write_title(ws, _('Caja / Fondo de ahorro'), formats, 15)
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado'), _('Importe')]; self._write_headers(ws, 5, headers, formats)
        row = 6; total = 0.0
        for slip in payslips:
            col = self._write_slip_common(ws, row, slip, formats); amount = self._line_total(slip, codes) if self.rule_codes else self._line_total_contains(slip, codes); ws.write(row, col, amount, formats['money']); total += amount; row += 1
        ws.write(row, 0, _('Total'), formats['bold']); ws.write(row, 12, total, formats['money']); ws.set_column(0, len(headers), 16)

    def _sheet_movements(self, workbook, formats):
        domain = [('company_id', '=', self.company_id.id), ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.employee_ids: domain.append(('employee_id', 'in', self.employee_ids.ids))
        if self.department_ids: domain.append(('employee_id.department_id', 'in', self.department_ids.ids))
        if not self.include_cancelled_movements: domain.append(('state', '!=', 'cancel'))
        incidences = self.env['rail.imss.incidence'].search(domain, order='date, employee_id')
        ws = workbook.add_worksheet('Altas y bajas'); self._write_title(ws, _('Altas y bajas IMSS'), formats, 14)
        headers = [_('Fecha'), _('Tipo'), _('Estado'), _('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('NSS'), _('RFC'), _('CURP'), _('Departamento'), _('SBC anterior'), _('SBC nuevo'), _('Notas')]; self._write_headers(ws, 5, headers, formats)
        row = 6
        for inc in incidences:
            emp = inc.employee_id; first, paternal, maternal = self._employee_split_name(emp)
            values = [inc.date, inc.incidence_type, inc.state, self._employee_number(emp), emp.name or '', first, paternal, maternal, getattr(emp, 'ssnid', '') or getattr(inc.version_id, 'ssnid', '') or '', getattr(emp, 'l10n_mx_rfc', '') or '', getattr(emp, 'l10n_mx_curp', '') or '', emp.department_id.display_name or '', inc.old_sbc or 0.0, inc.new_sbc or 0.0, inc.note or '']
            for col, value in enumerate(values): ws.write(row, col, value, formats['date'] if col == 0 else formats['money'] if col in (12, 13) else formats['text'])
            row += 1
        ws.set_column(0, len(headers), 16)

    def _sheet_liquidations(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes(['LIQ', 'SEVERANCE', 'FINIQUITO'])
        ws = workbook.add_worksheet('Liquidaciones'); self._write_title(ws, _('Liquidaciones'), formats, 16)
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado'), _('Bruto'), _('Neto'), _('Importe liquidación')]; self._write_headers(ws, 5, headers, formats)
        row = 6; total = 0.0
        for slip in payslips:
            amount = self._line_total(slip, codes) if self.rule_codes else (self._line_total_contains(slip, codes) or (slip.net_wage if 'LIQ' in (slip.struct_id.code or '').upper() else 0.0))
            if not amount: continue
            col = self._write_slip_common(ws, row, slip, formats); ws.write(row, col, slip.gross_wage, formats['money']); col += 1; ws.write(row, col, slip.net_wage, formats['money']); col += 1; ws.write(row, col, amount, formats['money']); total += amount; row += 1
        ws.write(row, 0, _('Total'), formats['bold']); ws.write(row, 14, total, formats['money']); ws.set_column(0, len(headers), 16)

    def _sheet_ptu(self, workbook, formats):
        payslips = self._get_payslips(); codes = self._parse_codes(['PTU', 'REPARTO', 'UTILIDADES'])
        ws = workbook.add_worksheet('PTU'); self._write_title(ws, _('PTU / Reparto de utilidades'), formats, 15)
        headers = [_('No. empleado'), _('Empleado'), _('Nombre'), _('Paterno'), _('Materno'), _('Departamento'), _('Versión'), _('Fecha inicial'), _('Fecha final'), _('Procesamiento'), _('Estructura'), _('Estado'), _('Importe PTU')]; self._write_headers(ws, 5, headers, formats)
        row = 6; total = 0.0
        for slip in payslips:
            amount = self._line_total(slip, codes) if self.rule_codes else self._line_total_contains(slip, codes)
            if not amount: continue
            col = self._write_slip_common(ws, row, slip, formats); ws.write(row, col, amount, formats['money']); total += amount; row += 1
        ws.write(row, 0, _('Total'), formats['bold']); ws.write(row, 12, total, formats['money']); ws.set_column(0, len(headers), 16)
