# -*- coding: utf-8 -*-

import base64
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    RAIL_MX_BANK_FORMATS = {
        'mx_bbva_mixed',
        'mx_bbva_only',
        'mx_banorte',
        'mx_santander_only',
        'mx_santander_mixed',
        'mx_banamex_c',
        'mx_banamex_d',
        'mx_banregio',
        'mx_hsbc',
        'mx_scotiabank',
        'mx_inbursa',
        'mx_banbajio',
    }

    export_format = fields.Selection(selection_add=[
        ('mx_bbva_mixed', 'BBVA Bancomer - Mixto'),
        ('mx_bbva_only', 'BBVA Bancomer - Solo BBVA'),
        ('mx_banorte', 'Banorte'),
        ('mx_santander_only', 'Santander - Solo Santander'),
        ('mx_santander_mixed', 'Santander - Mixto'),
        ('mx_banamex_c', 'Banamex - Dispersión C'),
        ('mx_banamex_d', 'Banamex - Dispersión D'),
        ('mx_banregio', 'Banregio'),
        ('mx_hsbc', 'HSBC'),
        ('mx_scotiabank', 'Scotiabank'),
        ('mx_inbursa', 'Inbursa'),
        ('mx_banbajio', 'Banbajío'),
    ], ondelete={
        'mx_bbva_mixed': 'set default',
        'mx_bbva_only': 'set default',
        'mx_banorte': 'set default',
        'mx_santander_only': 'set default',
        'mx_santander_mixed': 'set default',
        'mx_banamex_c': 'set default',
        'mx_banamex_d': 'set default',
        'mx_banregio': 'set default',
        'mx_hsbc': 'set default',
        'mx_scotiabank': 'set default',
        'mx_inbursa': 'set default',
        'mx_banbajio': 'set default',
    })

    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Cuenta de dispersión',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        check_company=True,
    )
    employee_filter = fields.Selection([
        ('all', 'Todos los empleados en el procesamiento'),
        ('same_bank', 'Empleados con mismo banco que la cuenta de dispersión'),
        ('different_bank', 'Empleados con diferente banco que la cuenta de dispersión'),
    ], string='Empleados a dispersar', default='all', required=True)

    payment_code = fields.Char('Código de pago')
    additional_data_2 = fields.Char('Dato adicional 2')
    additional_data_3 = fields.Char('Dato adicional 3')

    banamex_no_cliente = fields.Char('No. cliente Banamex')
    banamex_secuencia = fields.Char('Secuencia Banamex', default='1')
    banamex_descripcion = fields.Char('Descripción Banamex', default='Nomina')
    banamex_referencia = fields.Char('Referencia Banamex')
    banorte_numero = fields.Char('No. emisor asignado Banorte')
    bbva_referencia = fields.Char('Referencia BBVA (7 dígitos)')
    bbva_no_contrato = fields.Char('No. contrato BBVA (10 dígitos)')
    scotia_numero = fields.Char('Número de cliente Scotiabank')
    scotia_cuenta = fields.Char('Cuenta de cargo Scotiabank')
    scotia_referencia = fields.Char('Referencia Scotiabank')
    inbursa_cuenta = fields.Char('No. cuenta Inbursa')
    bajio_afinidad = fields.Char('Grupo afinidad Banbajío')

    def _is_rail_mx_format(self):
        self.ensure_one()
        return self.export_format in self.RAIL_MX_BANK_FORMATS

    def _perform_checks(self):
        super()._perform_checks()
        for wizard in self:
            if wizard._is_rail_mx_format():
                if not wizard.effective_date:
                    raise ValidationError(_('La fecha de dispersión es obligatoria.'))
                if not wizard.payment_journal_id:
                    raise ValidationError(_('La cuenta de dispersión es obligatoria para layouts bancarios mexicanos.'))
                if not wizard.payment_journal_id.bank_account_id:
                    raise ValidationError(_('La cuenta de dispersión no tiene cuenta bancaria configurada.'))
                wizard._rail_validate_required_layout_fields()

    def _rail_validate_required_layout_fields(self):
        self.ensure_one()
        required = {
            'mx_bbva_mixed': [('bbva_referencia', _('Referencia BBVA')), ('bbva_no_contrato', _('No. contrato BBVA'))],
            'mx_banorte': [('banorte_numero', _('No. emisor Banorte'))],
            'mx_banamex_c': [('banamex_no_cliente', _('No. cliente Banamex'))],
            'mx_banamex_d': [('banamex_no_cliente', _('No. cliente Banamex'))],
            'mx_scotiabank': [
                ('scotia_numero', _('Número de cliente Scotiabank')),
                ('scotia_cuenta', _('Cuenta de cargo Scotiabank')),
                ('scotia_referencia', _('Referencia Scotiabank')),
            ],
            'mx_banbajio': [('bajio_afinidad', _('Grupo afinidad Banbajío'))],
        }
        missing = [label for field_name, label in required.get(self.export_format, []) if not self[field_name]]
        if missing:
            raise ValidationError(_('Faltan datos obligatorios para el layout: %s') % ', '.join(missing))

    def generate_payment_report(self):
        self.ensure_one()
        if not self._is_rail_mx_format():
            return super().generate_payment_report()
        if self.payslip_ids.filtered('error_count'):
            raise ValidationError(self._get_error_message())
        self._perform_checks()
        self._write_payment_date()
        content, extension, filename = self._rail_generate_mx_bank_report()
        self._write_file(base64.b64encode(content), extension, filename=filename)

    # ---------------------------------------------------------------------
    # Data helpers
    # ---------------------------------------------------------------------

    def _rail_generate_mx_bank_report(self):
        self.ensure_one()
        payment_lines = self._rail_get_payment_lines()
        if not payment_lines:
            raise ValidationError(_('No hay información para generar el archivo de dispersión.'))
        method_name = '_rail_render_%s' % self.export_format.replace('mx_', '')
        renderer = getattr(self, method_name, False)
        if not renderer:
            raise ValidationError(_('No existe generador para el formato %s.') % self.export_format)
        return renderer(payment_lines)

    def _rail_get_payment_lines(self):
        self.ensure_one()
        lines = []
        source_bank = self.payment_journal_id.bank_account_id.bank_id
        for slip in self.payslip_ids.filtered(lambda p: p.state == 'validated' and p.net_wage > 0):
            allocations = slip.compute_salary_allocations() or {}
            if not allocations:
                continue
            for bank_account in slip.employee_id.bank_account_ids:
                amount = Decimal(str(allocations.get(str(bank_account.id), 0.0) or 0.0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if amount <= 0:
                    continue
                destination_bank = bank_account.bank_id
                same_bank = bool(source_bank and destination_bank and source_bank == destination_bank)
                if self.employee_filter == 'same_bank' and not same_bank:
                    continue
                if self.employee_filter == 'different_bank' and same_bank:
                    continue
                lines.append({
                    'sequence': len(lines) + 1,
                    'slip': slip,
                    'employee': slip.employee_id,
                    'bank_account': bank_account,
                    'bank': destination_bank,
                    'amount': amount,
                })
        return lines

    def _rail_company_name(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        return self._rail_clean_text(company.name or '', uppercase=False)

    def _rail_payslip_reference(self, line):
        """Return the payslip reference available in Odoo 19.

        The legacy payroll module exposed ``hr.payslip.number``. Native
        Odoo 19 no longer defines that field, so bank layouts must use the
        payslip name and fall back to the record display name/id.
        """
        slip = line['slip']
        return slip.name or slip.display_name or str(slip.id)

    def _rail_employee_number(self, line, required=True):
        number = line['employee'].registration_number or ''
        if required and not number:
            raise ValidationError(_('Falta número de empleado para %s.') % line['employee'].name)
        return str(number)

    def _rail_employee_rfc(self, line, required=True):
        employee = line['employee']
        rfc = employee.l10n_mx_rfc or employee.private_vat or ''
        if required and not rfc:
            raise ValidationError(_('Falta RFC para el empleado %s.') % employee.name)
        return str(rfc)

    def _rail_employee_split_name(self, line, required=False, join_with=' '):
        employee = line['employee']
        parts = employee.rail_get_split_legal_name() if hasattr(employee, 'rail_get_split_legal_name') else {}
        first = parts.get('first_name') or ''
        paternal = parts.get('paternal_surname') or ''
        maternal = parts.get('maternal_surname') or ''
        if required and (not first or not paternal):
            raise ValidationError(_('Falta nombre y/o apellido paterno para el empleado %s.') % employee.name)
        return join_with.join([part for part in [first, paternal, maternal] if part]) or employee.legal_name or employee.name

    def _rail_account_number(self, line, required=True):
        account = (line['bank_account'].acc_number or '').replace(' ', '').replace('-', '')
        if required and not account:
            raise ValidationError(_('Falta número de cuenta para el empleado %s.') % line['employee'].name)
        return account

    def _rail_account_type(self, line):
        account_type = line['bank_account'].rail_mx_account_type
        if account_type:
            return account_type
        account_number = self._rail_account_number(line, required=False)
        if len(account_number) == 18:
            return 'clabe'
        return 'checking'

    def _rail_bank_bic(self, bank):
        return (bank and bank.bic or '').strip()

    def _rail_bank_code(self, line, required=False):
        bank = line.get('bank')
        code = (bank.rail_mx_bank_code or bank.bic or '') if bank else ''
        if required and not code:
            raise ValidationError(_('El banco del empleado %s no tiene clave configurada.') % line['employee'].name)
        return code

    def _rail_clean_text(self, value, uppercase=True, banamex_ene=False):
        value = value or ''
        value = unicodedata.normalize('NFKD', value)
        value = ''.join(ch for ch in value if not unicodedata.combining(ch))
        if banamex_ene:
            value = value.replace('ñ', '@').replace('Ñ', '@')
        else:
            value = value.replace('ñ', 'n').replace('Ñ', 'N')
        value = re.sub(r"[/\-\.:\?&!']", '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        return value.upper() if uppercase else value

    def _rail_amount_parts(self, amount, int_size, cents_size=2):
        amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        integer, cents = ('%0.2f' % amount).split('.')
        return integer.rjust(int_size, '0'), cents.ljust(cents_size, '0')[:cents_size]

    def _rail_amount_compact(self, amount, size):
        amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        integer, cents = ('%0.2f' % amount).split('.')
        return (integer + cents).rjust(size, '0')

    def _rail_total(self, lines):
        return sum((line['amount'] for line in lines), Decimal('0.00'))

    def _rail_filename(self, extension):
        if self.export_format == 'mx_banorte':
            return 'NI%s01' % (self.banorte_numero or '')
        return fields.Datetime.now().strftime('%y%m-%d%H%M%S')

    def _rail_encode_lines(self, lines, extension='.txt'):
        text = '\n'.join(lines)
        return text.encode('utf-8'), extension, self._rail_filename(extension)

    # ---------------------------------------------------------------------
    # Renderers based on nomina_cfdi_bancos v18, adapted to Odoo 19 objects.
    # ---------------------------------------------------------------------

    def _rail_render_bbva_mixed(self, lines):
        total = self._rail_total(lines)
        int_total, cent_total = self._rail_amount_parts(total, 13)
        header = (
            '1'
            + str(len(lines)).rjust(7, '0')
            + int_total + cent_total
            + '0000000'
            + '000000000000000'
            + '000000000000'
            + (self.bbva_no_contrato or '')[:10].ljust(10, ' ')
            + 'R05'
            + '101'
            + '1'
            + fields.Date.today().strftime('%Y%m%d')
            + self.effective_date.strftime('%Y%m%d')
            + ''.ljust(142, ' ')
            + '\r'
        )
        output = [header]
        for line in lines:
            acc = self._rail_account_number(line)
            account_type = self._rail_account_type(line)
            if account_type in ('savings', 'clabe'):
                if len(acc) != 18:
                    raise ValidationError(_('BBVA mixto requiere CLABE de 18 dígitos para %s.') % line['employee'].name)
                type_code = '40'
                data5, data6, data7 = acc[:3], acc[3:6], acc[6:].rjust(16, '0')
            elif account_type == 'checking':
                if len(acc) != 10:
                    raise ValidationError(_('BBVA mixto requiere cuenta BBVA de 10 dígitos para %s.') % line['employee'].name)
                type_code = '01'
                data5, data6, data7 = '001', '001', acc.rjust(16, '0')
            else:
                raise ValidationError(_('Tipo de cuenta no permitido para BBVA mixto en %s.') % line['employee'].name)
            integer, cents = self._rail_amount_parts(line['amount'], 13)
            name = self._rail_clean_text(line['employee'].name)[0:40].ljust(40, ' ')
            output.append(
                '3'
                + (self.bbva_referencia or '')[:7].ljust(7, ' ')
                + self._rail_employee_rfc(line).ljust(18, ' ')
                + type_code + data5 + data6 + data7
                + integer + cents
                + '0000000'
                + ''.ljust(80, ' ')
                + name
                + 'PAGO POR CONCEPTO DE NOMINA'.ljust(40, ' ')
                + '\r'
            )
        return self._rail_encode_lines(output)

    def _rail_render_bbva_only(self, lines):
        output = []
        for index, line in enumerate(lines, start=1):
            acc = self._rail_account_number(line)
            account_type = self._rail_account_type(line)
            if account_type in ('savings', 'clabe'):
                if len(acc) != 18:
                    raise ValidationError(_('BBVA solo BBVA requiere CLABE de 18 dígitos para %s.') % line['employee'].name)
                type_code = '40'
                bank_prefix, plaza = acc[:3], acc[3:6]
            elif account_type == 'checking':
                if len(acc) != 10:
                    raise ValidationError(_('BBVA solo BBVA requiere cuenta de 10 dígitos para %s.') % line['employee'].name)
                type_code = '99'
                bank_prefix, plaza = '001', '001'
            else:
                raise ValidationError(_('Tipo de cuenta no permitido para BBVA solo BBVA en %s.') % line['employee'].name)
            integer, cents = self._rail_amount_parts(line['amount'], 13)
            name = self._rail_clean_text(line['employee'].name)[0:40].ljust(40, ' ')
            output.append(
                str(index).zfill(9)
                + self._rail_employee_rfc(line).ljust(16, ' ')[:16]
                + type_code
                + acc.ljust(20, ' ')
                + integer + cents
                + name
                + bank_prefix + plaza
                + '\r'
            )
        return self._rail_encode_lines(output)

    def _rail_render_santander_only(self, lines):
        source_acc = (self.payment_journal_id.bank_account_id.acc_number or '').ljust(16, ' ')[:16]
        output = [
            '1' + str(1).rjust(5, '0') + 'E'
            + fields.Date.today().strftime('%m%d%Y')
            + source_acc
            + self.effective_date.strftime('%m%d%Y')
        ]
        total = self._rail_total(lines)
        record_no = 2
        for line in lines:
            parts = line['employee'].rail_get_split_legal_name()
            if not parts.get('first_name') or not parts.get('paternal_surname'):
                raise ValidationError(_('Falta nombre y/o apellido paterno para %s.') % line['employee'].name)
            acc = self._rail_account_number(line).ljust(16, ' ')[:16]
            integer, cents = self._rail_amount_parts(line['amount'], 16)
            output.append(
                '2'
                + str(record_no).zfill(5)
                + self._rail_employee_number(line).ljust(7, ' ')[:7]
                + self._rail_clean_text(parts.get('paternal_surname'), uppercase=False).ljust(30, ' ')[:30]
                + self._rail_clean_text(parts.get('maternal_surname'), uppercase=False).ljust(20, ' ')[:20]
                + self._rail_clean_text(parts.get('first_name'), uppercase=False).ljust(30, ' ')[:30]
                + acc
                + integer + cents
                + (self.payment_code or '')
            )
            record_no += 1
        int_total, cents_total = self._rail_amount_parts(total, 16)
        output.append('3' + str(record_no).rjust(5, '0') + str(len(lines)).rjust(5, '0') + int_total + cents_total)
        return self._rail_encode_lines(output)

    def _rail_render_santander_mixed(self, lines):
        source_acc = (self.payment_journal_id.bank_account_id.acc_number or '').ljust(16, ' ')[:16]
        output = [
            '1' + str(1).rjust(5, '0') + 'E'
            + fields.Date.today().strftime('%m%d%Y')
            + source_acc
            + self.effective_date.strftime('%m%d%Y')
        ]
        total = self._rail_total(lines)
        record_no = 2
        for line in lines:
            acc = self._rail_account_number(line)
            account_type = self._rail_account_type(line)
            type_code = {
                'debit_card': '   02',
                'credit_card': '   02',
                'checking': '   01',
                'savings': '   40',
                'clabe': '   40',
            }.get(account_type)
            if not type_code:
                raise ValidationError(_('Tipo de cuenta no permitido para Santander mixto en %s.') % line['employee'].name)
            bank_code = (line['bank_account'].rail_santander_bank_code or self._rail_bank_code(line) or '').rjust(5, '0')[:5]
            place_code = (line['bank_account'].rail_santander_place_code or '').rjust(5, '0')[:5]
            if not place_code.strip('0'):
                raise ValidationError(_('Falta plaza Santander/Banxico para la cuenta de %s.') % line['employee'].name)
            output.append(
                '2'
                + str(record_no).zfill(5)
                + self._rail_clean_text(line['employee'].name, uppercase=False)[0:50].ljust(50, ' ')
                + type_code
                + acc.ljust(20, ' ')
                + self._rail_amount_compact(line['amount'], 18)
                + bank_code
                + place_code
            )
            record_no += 1
        int_total, cents_total = self._rail_amount_parts(total, 16)
        output.append('3' + str(record_no).rjust(5, '0') + str(len(lines)).rjust(5, '0') + int_total + cents_total)
        return self._rail_encode_lines(output)

    def _rail_render_banamex_c(self, lines):
        total = self._rail_total(lines)
        output = [
            '1'
            + (self.banamex_no_cliente or '').rjust(12, '0')
            + self.effective_date.strftime('%d%m%y')
            + (self.banamex_secuencia or '1').rjust(4, '0')
            + self._rail_company_name()[0:36].ljust(36, ' ')
            + (self.banamex_descripcion or 'Nomina').ljust(20, ' ')[:20]
            + ('05' if self.employee_filter == 'same_bank' else '07')
            + ''.ljust(40, ' ')
            + 'C00'
        ]
        for index, line in enumerate(lines, start=1):
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 16)
            name = self._rail_clean_text(self._rail_employee_split_name(line, required=True, join_with=','), banamex_ene=True)
            low_ref = str(index).rjust(10, '0') if self.employee_filter == 'same_bank' else '000000000000000000000000000000'
            high_ref = '                              ' if self.employee_filter == 'same_bank' else str(index).rjust(10, '0')
            bank_code = '    ' if self.employee_filter == 'same_bank' else '0' + acc[0:3]
            low_value_ref = '       ' if self.employee_filter == 'same_bank' else str(index).rjust(7, '0')
            output.append(
                '3' + '0' + '001'
                + integer + cents
                + '01'
                + acc.rjust(20, '0')
                + low_ref + high_ref
                + name[0:55].ljust(55, ' ')
                + 'TRANSFERENCIA'.ljust(40, ' ')
                + ''.ljust(24, ' ')
                + bank_code
                + low_value_ref
                + '  '
            )
        int_total, cents_total = self._rail_amount_parts(total, 16)
        source_acc = self.payment_journal_id.bank_account_id.acc_number or ''
        output.insert(1,
            '2' + '1' + '001'
            + int_total + cents_total
            + '01'
            + source_acc[0:4] + source_acc[4:].rjust(20, '0')
            + ''.ljust(20, ' ')
        )
        output.append('4' + '001' + str(len(lines)).rjust(6, '0') + int_total + cents_total + '000001' + int_total + cents_total)
        return self._rail_encode_lines(output)

    def _rail_render_banamex_d(self, lines):
        total = self._rail_total(lines)
        output = [
            '1'
            + (self.banamex_no_cliente or '').rjust(12, '0')
            + self.effective_date.strftime('%y%m%d')
            + '0001'
            + self._rail_company_name()[0:36].ljust(36, ' ')
            + (self.banamex_descripcion or 'Nomina').ljust(20, ' ')[:20]
            + '15D01'
        ]
        for index, line in enumerate(lines, start=1):
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 16)
            name = self._rail_clean_text(self._rail_employee_split_name(line, required=True, join_with=','), banamex_ene=True)
            output.append(
                '3' + '0' + '001' + '01' + '001'
                + integer + cents
                + '03'
                + '0000'
                + acc.ljust(16, ' ')
                + ('TRANSFER%s' % index).ljust(16, ' ')
                + name[0:55].ljust(55, ' ')
                + ''.ljust(35, ' ')
                + ''.ljust(35, ' ')
                + ''.ljust(35, ' ')
                + ''.ljust(35, ' ')
                + '0000'
                + '00'
                + ''.ljust(76, ' ')
                + ''.ljust(76, ' ')
            )
        int_total, cents_total = self._rail_amount_parts(total, 16)
        source_acc = self.payment_journal_id.bank_account_id.acc_number or ''
        output.insert(1, '2' + '1' + '001' + int_total + cents_total + '01' + source_acc.rjust(20, '0') + str(len(lines)).rjust(6, '0'))
        output.append('4' + '001' + str(len(lines)).rjust(6, '0') + int_total + cents_total + '000001' + int_total + cents_total)
        return self._rail_encode_lines(output)

    def _rail_render_banorte(self, lines):
        total = self._rail_total(lines)
        int_total, cents_total = self._rail_amount_parts(total, 13)
        output = [
            'HNE'
            + (self.banorte_numero or '')
            + self.effective_date.strftime('%Y%m%d')
            + '01'
            + str(len(lines)).rjust(6, '0')
            + int_total + cents_total
            + '000000'
            + '000000000000000'
            + '000000'
            + '000000000000000'
            + '000000'
            + '0'
            + '0' * 77
        ]
        for line in lines:
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 13)
            account_type = self._rail_account_type(line)
            type_code = '03' if account_type in ('debit_card', 'credit_card') else '01' if account_type == 'checking' else '40'
            output.append(
                'D'
                + self.effective_date.strftime('%Y%m%d')
                + self._rail_employee_number(line).rjust(10, '0')
                + ''.ljust(40, ' ')
                + ''.ljust(40, ' ')
                + integer + cents
                + self._rail_bank_code(line, required=True)[:3].rjust(3, '0')
                + type_code
                + acc.rjust(18, '0')
                + '0'
                + ' '
                + '00000000'
                + ''.ljust(18, ' ')
            )
        return self._rail_encode_lines(output, extension='.pag')

    def _rail_render_banregio(self, lines):
        output = []
        for index, line in enumerate(lines, start=1):
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 13)
            output.append(str(index).rjust(5, '0') + ',S,' + acc.rjust(20, '0') + ',' + integer + ',' + cents + ',0000000000000,00,TRANSFERENCIA SPEI                      ,' + ''.ljust(15, ' '))
        return self._rail_encode_lines(output, extension='.csv')

    def _rail_render_hsbc(self, lines):
        total = self._rail_total(lines)
        source_acc = self.payment_journal_id.bank_account_id.acc_number or ''
        int_total, cents_total = self._rail_amount_parts(total, 12)
        output = ['MXPRLF,F,' + source_acc.rjust(10, '0') + ',' + int_total + cents_total + ',' + str(len(lines)).rjust(7, '0') + ',' + self.effective_date.strftime('%d%m%Y') + ',,' + (self.payslip_run_id.name if self.payslip_run_id else '')]
        for line in lines:
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 12)
            name = self._rail_clean_text(self._rail_employee_split_name(line, required=True, join_with=' '), banamex_ene=True)[0:35].ljust(35, ' ')
            output.append(acc.rjust(10, '0') + ',' + integer + cents + ',ABONO POR PAGO DE NOMINA          ,' + name)
        return self._rail_encode_lines(output, extension='.csv')

    def _rail_render_scotiabank(self, lines):
        total = self._rail_total(lines)
        output = [
            'EEHA' + (self.scotia_numero or '').rjust(5, '0') + '01000000000000000000000000000' + ''.ljust(332, ' '),
            'EEHB' + (self.scotia_cuenta or '').rjust(17, '0') + '0000000001000' + ''.ljust(336, ' '),
        ]
        for line in lines:
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 15)
            name = self._rail_clean_text(self._rail_employee_split_name(line, required=True, join_with=' '), banamex_ene=True)[0:35].rjust(59, ' ')
            output.append(
                'EEDA04'
                + integer + cents
                + self.effective_date.strftime('%Y%m%d')
                + '01'
                + self._rail_employee_number(line).ljust(2, ' ')[:2]
                + name
                + ''.ljust(12, ' ')
                + (self.scotia_referencia or '').rjust(16, '0')
                + acc.rjust(30, '0')
                + '00000'
                + ''.ljust(40, ' ')
                + '1 '
                + '00000044044001'
                + '01'
                + ((self.payslip_run_id.name if self.payslip_run_id else '') or '').ljust(142, ' ')
                + '0' * 25
                + ''.ljust(22, ' ')
            )
        integer_total, cents_total = self._rail_amount_parts(total, 15)
        output.append('EETB' + '0000006' + integer_total + cents_total + '0' * 219 + ''.ljust(123, ' '))
        return self._rail_encode_lines(output)

    def _rail_inbursa_employee_number(self, line):
        """Return the numeric employee code required by Inbursa (max. 10 digits)."""
        employee_number = self._rail_employee_number(line)
        if not employee_number.isdigit():
            raise ValidationError(_(
                'El número de empleado de %(employee)s debe contener únicamente dígitos para el layout Inbursa. Valor actual: %(value)s'
            ) % {
                'employee': line['employee'].display_name,
                'value': employee_number,
            })
        if len(employee_number) > 10:
            raise ValidationError(_(
                'El número de empleado de %(employee)s excede el máximo de 10 dígitos requerido por Inbursa. Valor actual: %(value)s'
            ) % {
                'employee': line['employee'].display_name,
                'value': employee_number,
            })
        return employee_number

    def _rail_inbursa_employee_name(self, line):
        """Return a delimiter-safe employee name, limited to 50 characters."""
        name = self._rail_employee_split_name(line, required=True, join_with=' ')
        name = self._rail_clean_text(name)
        name = re.sub(r'[,\t\r\n]+', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        if not name:
            raise ValidationError(_(
                'Falta el nombre del empleado %s para el layout Inbursa.'
            ) % line['employee'].display_name)
        return name[:50]

    def _rail_inbursa_account(self, line):
        """Return the 11-digit credit account required by the supplied Inbursa layout."""
        account = self._rail_account_number(line)
        if not account.isdigit():
            raise ValidationError(_(
                'La cuenta de abono de %(employee)s debe contener únicamente dígitos para el layout Inbursa. Valor actual: %(value)s'
            ) % {
                'employee': line['employee'].display_name,
                'value': account,
            })
        if len(account) != 11:
            raise ValidationError(_(
                'La cuenta de abono de %(employee)s debe tener exactamente 11 dígitos para el layout Inbursa. Valor actual: %(value)s (%(length)s dígitos).'
            ) % {
                'employee': line['employee'].display_name,
                'value': account,
                'length': len(account),
            })
        return account

    def _rail_inbursa_amount(self, line):
        """Return a positive amount with two decimals and at most 15 numeric digits."""
        amount = Decimal(str(line['amount'] or 0)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if amount <= 0:
            raise ValidationError(_(
                'El monto de %(employee)s debe ser mayor que cero para el layout Inbursa.'
            ) % {'employee': line['employee'].display_name})
        amount_text = format(amount, '.2f')
        digit_count = len(amount_text.replace('.', '').replace('-', ''))
        if digit_count > 15:
            raise ValidationError(_(
                'El monto de %(employee)s excede el máximo de 15 dígitos requerido por Inbursa. Valor actual: %(value)s'
            ) % {
                'employee': line['employee'].display_name,
                'value': amount_text,
            })
        return amount_text

    def _rail_render_inbursa(self, lines):
        """Generate the five-column Inbursa payroll layout.

        Columns, without header or summary:
        consecutive, employee number, employee name, credit account, amount.
        """
        if len(lines) > 99999:
            raise ValidationError(_(
                'El layout Inbursa permite como máximo 99,999 registros por archivo.'
            ))

        output = []
        for index, line in enumerate(lines, start=1):
            output.append(','.join([
                str(index),
                self._rail_inbursa_employee_number(line),
                self._rail_inbursa_employee_name(line),
                self._rail_inbursa_account(line),
                self._rail_inbursa_amount(line),
            ]))

        content = '\r\n'.join(output).encode('utf-8')
        extension = '.txt'
        return content, extension, self._rail_filename(extension)

    def _rail_render_banbajio(self, lines):
        total = self._rail_total(lines)
        source_acc = self.payment_journal_id.bank_account_id.acc_number or ''
        output = [
            '010000001030S900'
            + (self.bajio_afinidad or '').rjust(7, '0')
            + fields.Date.today().strftime('%Y%m%d')
            + source_acc.rjust(20, '0')
            + ''.ljust(130, ' ')
        ]
        record_no = 2
        for line in lines:
            acc = self._rail_account_number(line)
            integer, cents = self._rail_amount_parts(line['amount'], 13)
            output.append(
                '02'
                + str(record_no).rjust(7, '0')
                + '90'
                + self.effective_date.strftime('%Y%m%d')
                + '000030'
                + integer + cents
                + self.effective_date.strftime('%Y%m%d')
                + '00'
                + source_acc.rjust(20, '0') + ' '
                + acc.rjust(22, '0') + ' '
                + str(record_no).rjust(7, '0')
                + 'DEPOSITO DE NOMINA                      '
                + '0' * 40
            )
            record_no += 1
        integer_total, cents_total = self._rail_amount_parts(total, 16)
        output.append('09' + str(record_no).rjust(7, '0') + '90' + str(len(lines)).rjust(7, '0') + integer_total + cents_total + ''.ljust(145, ' '))
        return self._rail_encode_lines(output)
