# -*- coding: utf-8 -*-

from collections import defaultdict

from markupsafe import Markup

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError


class ViaticosNomina(models.Model):
    _name = 'viaticos.nomina'
    _description = 'Viáticos de nómina'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char('Referencia', default=lambda self: _('Nuevo'), copy=False, tracking=True)
    fecha = fields.Date('Fecha', default=fields.Date.context_today, required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, tracking=True)
    version_id = fields.Many2one('hr.version', string='Versión laboral', compute='_compute_version_id', store=True, readonly=False)
    description = fields.Char('Descripción')
    entregas = fields.Float('Total entregas', compute='_compute_totals', store=True)
    comprobaciones = fields.Float('Total comprobaciones', compute='_compute_totals', store=True)
    por_comprobar = fields.Float('Por comprobar', compute='_compute_totals', store=True)
    observaciones = fields.Text('Observaciones')
    state = fields.Selection([
        ('draft', 'Generar entregas'),
        ('open', 'Generar comprobaciones'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', tracking=True)
    entregas_ids = fields.One2many('entregas.viaticos.nomina', 'viaticos_id', string='Entregas')
    comprobaciones_ids = fields.One2many('comprobaciones.viaticos.nomina', 'viaticos_id', string='Comprobaciones')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    # Se conservan los campos simples como referencia al último recibo generado.
    delivery_payslip_id = fields.Many2one('hr.payslip', string='Último recibo de entrega', copy=False)
    check_payslip_id = fields.Many2one('hr.payslip', string='Último recibo de comprobación', copy=False)
    delivery_payslip_run_id = fields.Many2one('hr.payslip.run', string='Último lote de entrega', copy=False)
    check_payslip_run_id = fields.Many2one('hr.payslip.run', string='Último lote de comprobación', copy=False)

    delivery_payslip_ids = fields.Many2many('hr.payslip', compute='_compute_linked_payslips', string='Recibos de entrega')
    check_payslip_ids = fields.Many2many('hr.payslip', compute='_compute_linked_payslips', string='Recibos de comprobación')
    delivery_payslip_count = fields.Integer(compute='_compute_linked_payslips')
    check_payslip_count = fields.Integer(compute='_compute_linked_payslips')

    @api.depends('employee_id', 'fecha')
    def _compute_version_id(self):
        for record in self:
            record.version_id = record.employee_id._get_version(record.fecha) if record.employee_id and record.fecha else False

    @api.depends('entregas_ids.importe', 'comprobaciones_ids.importe')
    def _compute_totals(self):
        for record in self:
            record.entregas = sum(record.entregas_ids.mapped('importe'))
            record.comprobaciones = sum(record.comprobaciones_ids.mapped('importe'))
            record.por_comprobar = record.entregas - record.comprobaciones

    @api.depends('entregas_ids.payslip_id', 'comprobaciones_ids.payslip_id')
    def _compute_linked_payslips(self):
        for record in self:
            delivery_slips = record.entregas_ids.payslip_id
            check_slips = record.comprobaciones_ids.payslip_id
            record.delivery_payslip_ids = delivery_slips
            record.check_payslip_ids = check_slips
            record.delivery_payslip_count = len(delivery_slips)
            record.check_payslip_count = len(check_slips)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                company = vals.get('company_id') or self.env.company.id
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('viaticos.nomina') or _('Nuevo')
        return super().create(vals_list)

    @api.constrains('employee_id', 'company_id')
    def _check_employee_company(self):
        for record in self:
            if record.employee_id and record.employee_id.company_id != record.company_id:
                raise UserError(_('El empleado y el viático deben pertenecer a la misma compañía.'))

    def _get_input_type(self, xmlid):
        input_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not input_type:
            raise UserError(_('No se encontró el tipo de input %s.') % xmlid)
        return input_type

    def _get_viaticos_structure(self, kind):
        xmlid = {
            'delivery': 'rail_l10n_mx_payroll_extras.structure_viaticos_delivery',
            'check': 'rail_l10n_mx_payroll_extras.structure_viaticos_check',
        }[kind]
        structure = self.env.ref(xmlid, raise_if_not_found=False)
        if not structure:
            raise UserError(_('No se encontró la estructura extraordinaria de viáticos: %s.') % xmlid)
        return structure

    def _get_pending_lines(self, kind):
        self.ensure_one()
        if kind == 'delivery':
            return self.entregas_ids.filtered(lambda line: line.cfdi and not line.generado and not line.payslip_id)
        return self.comprobaciones_ids.filtered(lambda line: line.cfdi and not line.generado and not line.payslip_id)

    @api.model
    def _create_viaticos_run(self, kind, company, run_date, structure):
        label = _('Entrega de viáticos') if kind == 'delivery' else _('Comprobación de viáticos')
        return self.env['hr.payslip.run'].create({
            'name': '%s - %s' % (label, fields.Date.to_string(run_date)),
            'date_start': run_date,
            'date_end': run_date,
            'structure_id': structure.id,
            'company_id': company.id,
            'schedule_pay': structure.type_id.default_schedule_pay,
        })

    def _prepare_viaticos_input_commands(self, kind, amount):
        self.ensure_one()
        if kind == 'delivery':
            delivery_input = self._get_input_type('rail_l10n_mx_payroll_extras.input_type_viaticos_delivery')
            return [Command.create({
                'name': _('Viáticos entregados'),
                'input_type_id': delivery_input.id,
                'amount': amount,
                'rail_viaticos_id': self.id,
                'rail_generated_by_extra': 'viaticos',
            })]

        check_input = self._get_input_type('rail_l10n_mx_payroll_extras.input_type_viaticos_check')
        adjustment_input = self._get_input_type('rail_l10n_mx_payroll_extras.input_type_viaticos_adjustment')
        return [
            Command.create({
                'name': _('Comprobación de viáticos'),
                'input_type_id': check_input.id,
                'amount': amount,
                'rail_viaticos_id': self.id,
                'rail_generated_by_extra': 'viaticos',
            }),
            Command.create({
                'name': _('Ajuste en viáticos entregados al trabajador'),
                'input_type_id': adjustment_input.id,
                'amount': amount,
                'rail_viaticos_id': self.id,
                'rail_generated_by_extra': 'viaticos',
            }),
        ]

    def _create_viaticos_payslip(self, kind, pending_lines, payslip_run, structure):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Seleccione empleado.'))
        version = self.employee_id._get_version(self.fecha)
        if not version:
            raise UserError(_(
                'No se encontró una versión laboral vigente para %(employee)s en la fecha %(date)s.'
            ) % {'employee': self.employee_id.display_name, 'date': self.fecha})

        amount = sum(pending_lines.mapped('importe'))
        if amount <= 0:
            raise UserError(_('El importe pendiente de %s debe ser mayor a cero.') % self.display_name)

        label = _('Entrega de viáticos') if kind == 'delivery' else _('Comprobación de viáticos')
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee_id.id,
            'version_id': version.id,
            'date_from': self.fecha,
            'date_to': self.fecha,
            'name': '%s - %s - %s' % (label, self.employee_id.display_name, self.name),
            'struct_id': structure.id,
            'payslip_run_id': payslip_run.id,
            'rail_apply_installments': False,
            'rail_viaticos_id': self.id,
            'rail_viaticos_kind': kind,
            'input_line_ids': self._prepare_viaticos_input_commands(kind, amount),
        })
        # El recibo queda en borrador, pero calculado y listo para revisión/validación/timbrado.
        payslip.compute_sheet()
        return payslip

    def _action_view_generated_payslips(self, payslips, title):
        if not payslips:
            return False
        if len(payslips) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': title,
                'res_model': 'hr.payslip',
                'view_mode': 'form',
                'res_id': payslips.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payslips.ids)],
        }

    def _generate_viaticos_payslips(self, kind):
        records_with_lines = self.filtered(lambda record: record._get_pending_lines(kind))
        if not records_with_lines:
            label = _('entregas') if kind == 'delivery' else _('comprobaciones')
            raise UserError(_('No hay líneas de %s con CFDI pendientes de generar.') % label)

        if kind == 'check':
            invalid = records_with_lines.filtered(lambda record: record.state == 'draft')
            if invalid:
                raise UserError(_(
                    'Primero genere la entrega de viáticos para: %s.'
                ) % ', '.join(invalid.mapped('display_name')))

        structure = self._get_viaticos_structure(kind)
        grouped_records = defaultdict(lambda: self.env['viaticos.nomina'])
        for record in records_with_lines:
            grouped_records[(record.company_id, record.fecha)] |= record

        generated_payslips = self.env['hr.payslip']
        for (company, run_date), viaticos_records in grouped_records.items():
            payslip_run = self._create_viaticos_run(kind, company, run_date, structure)
            for record in viaticos_records:
                pending_lines = record._get_pending_lines(kind)
                payslip = record._create_viaticos_payslip(kind, pending_lines, payslip_run, structure)
                generated_payslips |= payslip
                pending_lines.write({'generado': True, 'payslip_id': payslip.id})

                if kind == 'delivery':
                    record.write({
                        'delivery_payslip_id': payslip.id,
                        'delivery_payslip_run_id': payslip_run.id,
                        'state': 'open',
                    })
                else:
                    vals = {
                        'check_payslip_id': payslip.id,
                        'check_payslip_run_id': payslip_run.id,
                    }
                    if abs(record.por_comprobar) <= 0.01:
                        vals['state'] = 'closed'
                    record.write(vals)

                record.message_post(body=Markup(
                    '<p>Se generó el recibo extraordinario %s dentro del lote %s.</p>'
                ) % (payslip._get_html_link(), payslip_run._get_html_link()))

        title = _('Recibos extraordinarios de entrega de viáticos') if kind == 'delivery' else _(
            'Recibos extraordinarios de comprobación de viáticos'
        )
        return self._action_view_generated_payslips(generated_payslips, title)

    def action_generate_delivery_payslips(self):
        return self._generate_viaticos_payslips('delivery')

    def action_generate_check_payslips(self):
        return self._generate_viaticos_payslips('check')

    # Alias de compatibilidad con los botones y flujo v18.
    def action_validar(self):
        return self.action_generate_delivery_payslips()

    def action_cerrar(self):
        return self.action_generate_check_payslips()

    def action_view_delivery_payslip(self):
        payslips = self.entregas_ids.payslip_id
        return self._action_view_generated_payslips(payslips, _('Recibos de entrega de viáticos'))

    def action_view_check_payslip(self):
        payslips = self.comprobaciones_ids.payslip_id
        return self._action_view_generated_payslips(payslips, _('Recibos de comprobación de viáticos'))


class EntregasViaticosNomina(models.Model):
    _name = 'entregas.viaticos.nomina'
    _description = 'Entrega de viáticos'
    _order = 'fecha, id'

    fecha = fields.Date('Fecha')
    referencia = fields.Char('Referencia')
    cfdi = fields.Boolean('CFDI')
    generado = fields.Boolean('Generado', copy=False, readonly=True)
    importe = fields.Float('Importe')
    payslip_id = fields.Many2one('hr.payslip', string='Recibo extraordinario', copy=False, ondelete='set null', readonly=True)
    viaticos_id = fields.Many2one('viaticos.nomina', string='Viáticos', ondelete='cascade')


class ComprobacionesViaticosNomina(models.Model):
    _name = 'comprobaciones.viaticos.nomina'
    _description = 'Comprobación de viáticos'
    _order = 'fecha, id'

    fecha = fields.Date('Fecha')
    referencia = fields.Selection([
        ('01', 'CFDI'),
        ('02', 'Documentos no fiscales'),
        ('03', 'Efectivo'),
    ], string='Tipo')
    cfdi = fields.Boolean('CFDI')
    generado = fields.Boolean('Generado', copy=False, readonly=True)
    importe = fields.Float('Importe')
    payslip_id = fields.Many2one('hr.payslip', string='Recibo extraordinario', copy=False, ondelete='set null', readonly=True)
    viaticos_id = fields.Many2one('viaticos.nomina', string='Viáticos', ondelete='cascade')
