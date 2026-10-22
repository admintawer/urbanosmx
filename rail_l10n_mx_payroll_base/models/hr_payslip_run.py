# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    rail_payroll_alias = fields.Char(
        string='Alias de nómina',
        copy=False,
        index=True,
        tracking=True,
        help=(
            'Nombre operativo asignado manualmente al lote de nómina. '
            'No reemplaza el nombre técnico generado por Odoo en el campo name.'
        ),
    )
    rail_l10n_mx_payroll_type = fields.Selection(
        selection=[
            ('O', 'Nómina ordinaria'),
            ('E', 'Nómina extraordinaria'),
        ],
        string='Tipo de nómina',
        default='O',
        required=True,
        help=(
            'Tipo de nómina utilizado para limitar las estructuras salariales mexicanas '
            'disponibles en el lote. No sustituye al Calendario de pago (schedule_pay).'
        ),
    )
    rail_payroll_number = fields.Selection(
        selection=[
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
            ('5', '5'),
            ('6', '6'),
            ('7', '7'),
            ('8', '8'),
        ],
        string='Número de nómina',
        help=(
            'Número operativo de la nómina dentro del periodo. Se conserva como selección '
            'de 1 a 8, equivalente al comportamiento funcional de la versión anterior.'
        ),
    )
    rail_period_days = fields.Integer(
        string='Días del periodo',
        compute='_compute_rail_period_days',
        store=True,
        readonly=True,
        help='Cantidad de días calendario comprendidos entre el inicio y el fin del periodo, inclusive.',
    )

    @api.onchange('rail_l10n_mx_payroll_type')
    def _onchange_rail_l10n_mx_payroll_type(self):
        """Keep the native salary structure consistent with the selected MX payroll type."""
        for run in self:
            if (
                run.structure_id
                and 'l10n_mx_payroll_type' in run.structure_id._fields
                and run.structure_id.l10n_mx_payroll_type != run.rail_l10n_mx_payroll_type
            ):
                run.structure_id = False

    @api.constrains('structure_id', 'rail_l10n_mx_payroll_type')
    def _check_rail_l10n_mx_payroll_type_structure(self):
        for run in self:
            if not run.structure_id or not run.rail_l10n_mx_payroll_type:
                continue
            if 'l10n_mx_payroll_type' not in run.structure_id._fields:
                continue
            structure_type = run.structure_id.l10n_mx_payroll_type
            if structure_type and structure_type != run.rail_l10n_mx_payroll_type:
                raise ValidationError(_(
                    'La estructura salarial seleccionada no corresponde al tipo de nómina del lote.'
                ))

    @api.depends('date_start', 'date_end')
    def _compute_rail_period_days(self):
        for run in self:
            if run.date_start and run.date_end and run.date_end >= run.date_start:
                run.rail_period_days = (run.date_end - run.date_start).days + 1
            else:
                run.rail_period_days = 0
