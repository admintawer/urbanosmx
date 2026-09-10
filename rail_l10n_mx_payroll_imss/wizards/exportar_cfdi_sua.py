# -*- coding: utf-8 -*-

import base64
import re
from datetime import datetime
from urllib.parse import urlencode

from odoo import fields, models, _
from odoo.exceptions import UserError


class ExportarCfdiSua(models.TransientModel):
    _name = 'exportar.cfdi.sua'
    _description = 'Exportar SUA/IDSE'

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    export_target = fields.Selection([
        ('sua', 'SUA'),
        ('idse', 'IDSE'),
    ], string='Destino', required=True, default='sua')
    tipo_exp_sua = fields.Selection([
        ('0', 'Movimientos generales'),
        ('1', 'Datos incapacidades'),
        ('2', 'Alta trabajadores'),
        ('3', 'Datos afiliatorios'),
        ('4', 'Movimientos de crédito INFONAVIT'),
        ('5', 'Reingreso'),
        ('6', 'Faltas'),
        ('7', 'Baja'),
        ('8', 'Incapacidades'),
        ('9', 'Cambio de sueldo'),
    ], string='Tipo exportación SUA', default='0')
    tipo_exp_idse = fields.Selection([
        ('0', 'Alta / Reingreso'),
        ('1', 'Baja'),
        ('2', 'Cambio sueldo'),
    ], string='Tipo exportación IDSE', default='0')
    file_content = fields.Binary('Archivo', readonly=True)
    file_name = fields.Char('Nombre archivo', readonly=True)
    error_log = fields.Text('Resultado', readonly=True)

    def action_export(self):
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_('La fecha inicial no puede ser mayor a la fecha final.'))
        lines = self._build_idse_lines() if self.export_target == 'idse' else self._build_sua_lines()
        if not lines:
            raise UserError(self._get_no_data_message())

        file_text = '\r\n'.join(lines) + '\r\n'
        file_name = '%s_%s_%s.txt' % (
            self.export_target.upper(),
            self.start_date.strftime('%Y%m%d'),
            self.end_date.strftime('%Y%m%d'),
        )
        self.write({
            'file_content': base64.b64encode(file_text.encode('latin-1', errors='replace')),
            'file_name': file_name,
            'error_log': _('Registros generados: %s') % len(lines),
        })

        # En la versión anterior se reabría el mismo wizard. Cuando no había
        # líneas, file_content quedaba vacío y el grupo de descarga permanecía
        # invisible, por lo que para el usuario parecía que el botón no hacía
        # nada. Si hay datos, se descarga el archivo directamente; si no hay,
        # se muestra el UserError anterior.
        query = urlencode({
            'model': self._name,
            'id': self.id,
            'field': 'file_content',
            'filename_field': 'file_name',
            'download': 'true',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?%s' % query,
            'target': 'self',
        }

    def _get_no_data_message(self):
        self.ensure_one()
        if self.export_target == 'idse':
            selection = dict(self._fields['tipo_exp_idse'].selection)
            export_label = selection.get(self.tipo_exp_idse, self.tipo_exp_idse or '')
        else:
            selection = dict(self._fields['tipo_exp_sua'].selection)
            export_label = selection.get(self.tipo_exp_sua, self.tipo_exp_sua or '')

        incidence_count = self.env['rail.imss.incidence'].search_count(self._base_incidence_domain())
        absence_count = self.env['hr.leave'].search_count(self._base_leave_domain(disability=False))
        disability_count = self.env['hr.leave'].search_count(self._base_leave_domain(disability=True))
        guidance = ''
        if self.export_target == 'sua' and self.tipo_exp_sua == '6' and disability_count:
            guidance = _(
                '\n\nSe encontraron %(count)s incapacidad(es), pero la opción seleccionada es Faltas. '
                'Para exportarlas seleccione Tipo exportación SUA = Incapacidades.'
            ) % {'count': disability_count}
        elif self.export_target == 'sua' and self.tipo_exp_sua in ('1', '8') and absence_count:
            guidance = _(
                '\n\nSe encontraron %(count)s falta(s), pero la opción seleccionada corresponde a incapacidades. '
                'Para exportarlas seleccione Tipo exportación SUA = Faltas.'
            ) % {'count': absence_count}

        return _(
            'No se encontraron datos para generar %(target)s - %(export)s entre %(start)s y %(end)s.\n\n'
            'Incidencias IMSS confirmadas en el periodo: %(incidences)s.\n'
            'Faltas validadas con códigos FJS/FI/FR: %(absences)s.\n'
            'Incapacidades validadas con códigos INC_RT/INC_MAT/INC_EG: %(disabilities)s.\n\n'
            'Las incidencias deben estar en estado Confirmada y las ausencias en estado Validada.%(guidance)s'
        ) % {
            'target': (self.export_target or '').upper(),
            'export': export_label,
            'start': self.start_date,
            'end': self.end_date,
            'incidences': incidence_count,
            'absences': absence_count,
            'disabilities': disability_count,
            'guidance': guidance,
        }

    def _base_incidence_domain(self):
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('state', '=', 'done'),
        ]
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        return domain

    def _base_leave_domain(self, disability=False):
        domain = [
            ('request_date_from', '>=', self.start_date),
            ('request_date_from', '<=', self.end_date),
            ('state', '=', 'validate'),
        ]
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        if disability:
            domain.append(('holiday_status_id.code', 'in', ['INC_RT', 'INC_MAT', 'INC_EG']))
        else:
            domain.append(('holiday_status_id.code', 'in', ['FJS', 'FI', 'FR']))
        return domain

    def _build_idse_lines(self):
        incidence_types = {
            '0': ['hire', 'reentry'],
            '1': ['leave'],
            '2': ['salary_change'],
        }.get(self.tipo_exp_idse, [])
        incidences = self.env['rail.imss.incidence'].search(self._base_incidence_domain() + [('incidence_type', 'in', incidence_types)])
        lines = [self._format_idse_incidence_line(incidence) for incidence in incidences]
        incidences.write({'exported_idse': True})
        return lines

    def _build_sua_lines(self):
        lines = []
        if self.tipo_exp_sua in ('0', '2', '5', '7', '9'):
            incidence_types = {
                '0': ['hire', 'reentry', 'leave', 'salary_change'],
                '2': ['hire'],
                '5': ['reentry'],
                '7': ['leave'],
                '9': ['salary_change'],
            }.get(self.tipo_exp_sua, [])
            incidences = self.env['rail.imss.incidence'].search(self._base_incidence_domain() + [('incidence_type', 'in', incidence_types)])
            lines += [self._format_sua_incidence_line(incidence) for incidence in incidences]
            incidences.write({'exported_sua': True})
        if self.tipo_exp_sua in ('0', '6'):
            leaves = self.env['hr.leave'].search(self._base_leave_domain(disability=False))
            lines += [self._format_sua_absence_line(leave) for leave in leaves]
            leaves.write({'rail_imss_exported': True})
        if self.tipo_exp_sua in ('0', '1', '8'):
            leaves = self.env['hr.leave'].search(self._base_leave_domain(disability=True))
            lines += [self._format_sua_disability_line(leave) for leave in leaves]
            leaves.write({'rail_imss_exported': True})
        if self.tipo_exp_sua == '3':
            incidences = self.env['rail.imss.incidence'].search(
                self._base_incidence_domain() + [('incidence_type', '=', 'hire')]
            )
            lines += [self._format_sua_affiliation_line(incidence) for incidence in incidences]
            incidences.write({'exported_sua': True})
        if self.tipo_exp_sua == '4':
            lines += self._format_sua_infonavit_lines()
        return lines

    def _format_idse_incidence_line(self, incidence):
        employee = incidence.employee_id
        version = incidence.version_id
        values = self._validated_employee_values(employee, version)
        movement_code = {
            'hire': '08',
            'reentry': '08',
            'leave': '02',
            'salary_change': '07',
        }.get(incidence.incidence_type, '  ')
        sbc = incidence.new_sbc or version.rail_fixed_sbc or 0.0
        return ''.join([
            self._clean(values['registration_patronal'], 11, ' '),
            self._clean(values['ssn'], 11, '0'),
            self._clean(employee.rail_paternal_surname or '', 27, ' '),
            self._clean(employee.rail_maternal_surname or '', 27, ' '),
            self._clean(employee.rail_first_name or employee.name or '', 27, ' '),
            self._amount_cents(sbc, 6),
            self._clean(employee.rail_imss_worker_type or '', 1, ' '),
            self._clean(employee.rail_imss_salary_type or '', 1, ' '),
            self._clean(employee.rail_imss_workday_type or '', 1, ' '),
            incidence.date.strftime('%d%m%Y'),
            self._clean(employee.rail_imss_clinic or '', 3, ' '),
            movement_code,
        ])

    def _format_sua_incidence_line(self, incidence):
        employee = incidence.employee_id
        version = incidence.version_id
        values = self._validated_employee_values(employee, version)
        movement_code = {
            'hire': '08',
            'reentry': '08',
            'leave': '02',
            'salary_change': '07',
        }.get(incidence.incidence_type, '00')
        sbc = incidence.new_sbc or version.rail_fixed_sbc or 0.0
        return '|'.join([
            values['registration_patronal'],
            values['ssn'],
            movement_code,
            incidence.date.strftime('%d/%m/%Y'),
            '%.2f' % sbc,
            employee.rail_imss_worker_type or '',
            employee.rail_imss_salary_type or '',
            employee.rail_imss_workday_type or '',
        ])

    def _format_sua_absence_line(self, leave):
        employee = leave.employee_id
        values = self._validated_employee_values(employee, employee.version_id)
        days = int(round(leave.number_of_days or 0))
        return '|'.join([
            values['registration_patronal'],
            values['ssn'],
            'FALTA',
            leave.request_date_from.strftime('%d/%m/%Y'),
            str(days),
            leave.holiday_status_id.code or '',
        ])

    def _format_sua_disability_line(self, leave):
        employee = leave.employee_id
        values = self._validated_employee_values(employee, employee.version_id)
        if not leave.rail_imss_disability_folio:
            raise UserError(_('La incapacidad de %s no tiene folio IMSS.') % employee.display_name)
        days = int(round(leave.number_of_days or 0))
        return '|'.join([
            values['registration_patronal'],
            values['ssn'],
            'INCAPACIDAD',
            leave.request_date_from.strftime('%d/%m/%Y'),
            str(days),
            leave.rail_imss_disability_branch or '',
            leave.rail_imss_risk_type or '',
            leave.rail_imss_disability_folio or '',
            str(leave.rail_imss_percentage or 0.0),
        ])


    def _format_sua_affiliation_line(self, incidence):
        employee = incidence.employee_id
        version = incidence.version_id
        values = self._validated_employee_values(employee, version)

        private_zip = (employee.private_zip or '').strip()
        if len(private_zip) != 5:
            raise UserError(
                _('El empleado %s debe tener un código postal privado de 5 dígitos.')
                % employee.display_name
            )
        if not employee.birthday:
            raise UserError(_('El empleado %s no tiene fecha de nacimiento.') % employee.display_name)
        if not employee.place_of_birth:
            raise UserError(_('El empleado %s no tiene lugar de nacimiento.') % employee.display_name)
        if not employee.rail_imss_clinic:
            raise UserError(_('El empleado %s no tiene unidad de medicina familiar.') % employee.display_name)
        job_title = version.job_title or employee.job_title or ''
        if not job_title:
            raise UserError(_('El empleado %s no tiene puesto configurado.') % employee.display_name)
        gender = {'male': 'M', 'female': 'F'}.get(version.sex)
        if not gender:
            raise UserError(_('El empleado %s debe tener sexo legal masculino o femenino para el layout SUA.') % employee.display_name)
        if not employee.rail_imss_salary_type:
            raise UserError(_('El empleado %s no tiene tipo de salario SUA configurado.') % employee.display_name)

        return ''.join([
            self._clean(values['registration_patronal'], 11, ' '),
            self._clean(values['ssn'], 11, '0'),
            private_zip,
            employee.birthday.strftime('%d%m%Y'),
            self._clean_right(employee.place_of_birth, 25),
            '00',
            self._clean(employee.rail_imss_clinic, 3, ' '),
            self._clean_right(job_title, 12),
            gender,
            employee.rail_imss_salary_type,
            ' ',
        ])

    def _format_sua_infonavit_lines(self):
        domain = [('status', '=', 'in_progress')]
        if self.employee_id:
            domain.append(('version_id.employee_id', '=', self.employee_id.id))
        credits = self.env['l10n.mx.hr.infonavit'].search(domain)
        lines = []
        for credit in credits:
            employee = credit.version_id.employee_id
            values = self._validated_employee_values(employee, credit.version_id)
            lines.append('|'.join([
                values['registration_patronal'],
                values['ssn'],
                'INFONAVIT',
                credit.infonavit_type or '',
                '%.2f' % (credit.fixed_monetary_fee or credit.percentage or credit.discount_factor or 0.0),
                '%.2f' % (credit.monthly_insurance or 0.0),
            ]))
        return lines

    def _validated_employee_values(self, employee, version):
        registration_patronal = employee.company_id.l10n_mx_imss_id or ''
        if not registration_patronal:
            raise UserError(_('La compañía %s no tiene registro patronal IMSS configurado.') % employee.company_id.display_name)
        ssn = employee.ssnid or ''
        if not ssn:
            raise UserError(_('El empleado %s no tiene NSS configurado.') % employee.display_name)
        if not employee.rail_first_name:
            raise UserError(_('El empleado %s no tiene nombre separado configurado.') % employee.display_name)
        return {
            'registration_patronal': registration_patronal,
            'ssn': ssn,
        }

    def _clean(self, value, size, fill=' '):
        text = str(value or '').upper().replace('Ñ', '#').replace('ñ', '#')
        text = re.sub(r'[^A-Z0-9# .,/\-]', ' ', text)
        return text[:size].ljust(size, fill)

    def _clean_right(self, value, size, fill=' '):
        text = str(value or '').upper().replace('Ñ', '#').replace('ñ', '#')
        text = re.sub(r'[^A-Z0-9# .,/\-]', ' ', text)
        return text[-size:].rjust(size, fill)

    def _amount_cents(self, amount, size):
        return str(int(round((amount or 0.0) * 100))).zfill(size)[-size:]
