# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round


class RailVacationLine(models.Model):
    _name = 'rail.vacation.line'
    _description = 'Saldo vacacional MX por versión laboral'
    _order = 'employee_id, anniversary_date desc, year desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Descripción', compute='_compute_display_name', store=True)
    version_id = fields.Many2one(
        'hr.version',
        string='Versión laboral',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        related='version_id.employee_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='version_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    year = fields.Char(string='Año de vigencia', required=True, index=True)
    seniority_start_date = fields.Date(
        string='Inicio de antigüedad',
        index=True,
        help='Primera fecha de contrato usada para calcular este saldo.',
    )
    seniority_years = fields.Integer(
        string='Años de antigüedad',
        help='Años completos reconocidos al generar el saldo.',
    )
    anniversary_date = fields.Date(
        string='Fecha de aniversario',
        index=True,
        help='Aniversario laboral que originó este saldo.',
    )
    state = fields.Selection([
        ('active', 'Activo'),
        ('closed', 'Cerrado'),
        ('expired', 'Vencido'),
    ], string='Estado', default='active', required=True, index=True)
    origin = fields.Selection([
        ('auto', 'Automático'),
        ('manual', 'Manual'),
        ('migration', 'Migración'),
    ], string='Origen', default='manual', required=True)
    granted_days = fields.Float(string='Días otorgados', digits='Payroll', required=True, default=0.0)
    used_days = fields.Float(string='Días usados', digits='Payroll', default=0.0)
    remaining_days = fields.Float(string='Días disponibles', digits='Payroll', compute='_compute_remaining_days', store=True)
    note = fields.Text(string='Notas')

    _rail_vacation_line_version_year_unique = models.Constraint(
        'UNIQUE(version_id, year)',
        'Ya existe una línea vacacional para esta versión y año.',
    )

    _rail_vacation_line_days_positive = models.Constraint(
        'CHECK(granted_days >= 0 AND used_days >= 0)',
        'Los días otorgados y usados no pueden ser negativos.',
    )

    _rail_vacation_line_seniority_positive = models.Constraint(
        'CHECK(seniority_years >= 0)',
        'Los años de antigüedad no pueden ser negativos.',
    )

    @api.depends('year', 'seniority_years', 'granted_days', 'used_days', 'state')
    def _compute_display_name(self):
        for line in self:
            remaining = float_round(line.remaining_days, precision_digits=2)
            line.display_name = _(
                '[%(year)s] %(days)s días disponibles · %(seniority)s años',
                year=line.year or '-',
                days=remaining,
                seniority=line.seniority_years or 0,
            )

    @api.depends('granted_days', 'used_days')
    def _compute_remaining_days(self):
        for line in self:
            line.remaining_days = max((line.granted_days or 0.0) - (line.used_days or 0.0), 0.0)

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_expire(self):
        self.write({'state': 'expired'})


class RailVacationLeaveConsumption(models.Model):
    _name = 'rail.vacation.leave.consumption'
    _description = 'Consumo de vacaciones por ausencia'
    _order = 'leave_id, id'

    leave_id = fields.Many2one('hr.leave', string='Ausencia', required=True, ondelete='cascade', index=True)
    vacation_line_id = fields.Many2one('rail.vacation.line', string='Línea vacacional', required=True, ondelete='cascade', index=True)
    days = fields.Float(string='Días consumidos', digits='Payroll', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', related='leave_id.employee_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', related='leave_id.company_id', store=True, readonly=True)
