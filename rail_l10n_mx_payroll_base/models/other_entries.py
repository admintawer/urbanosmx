# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RailPayrollOtherEntryType(models.Model):
    _name = 'rail.payroll.other.entry.type'
    _description = 'Tipo de otra entrada de nómina'
    _order = 'code, name'

    name = fields.Char(
        string='Tipo de entrada',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Código',
        required=True,
        index=True,
        help='Código utilizado por las reglas salariales para identificar esta entrada.',
    )
    default_amount = fields.Float(
        string='Monto predeterminado',
        digits='Payroll',
        help=(
            'Valor sugerido al seleccionar este tipo en la ficha del empleado. '
            'Se copia a la línea del empleado y después puede modificarse sin alterar este catálogo.'
        ),
    )
    default_percentage = fields.Float(
        string='Porcentaje predeterminado (%)',
        digits='Payroll Rate',
        help=(
            'Porcentaje sugerido al seleccionar este tipo en la ficha del empleado. '
            'Capture 6 para representar 6%. El valor se copia a la línea y no queda ligado al catálogo.'
        ),
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Desactive el tipo para impedir nuevas capturas sin eliminar su historial.',
    )

    _rail_other_entry_type_code_unique = models.Constraint(
        'UNIQUE(code)',
        'El código del tipo de entrada debe ser único.',
    )


class RailPayrollOtherEntry(models.Model):
    _name = 'rail.payroll.other.entry'
    _description = 'Otra entrada de nómina del empleado'
    _order = 'employee_id, active desc, code, id'
    _rec_name = 'description'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    entry_type_id = fields.Many2one(
        'rail.payroll.other.entry.type',
        string='Tipo de entrada',
        required=True,
        ondelete='restrict',
        index=True,
    )
    description = fields.Char(
        string='Descripción',
        related='entry_type_id.name',
        store=True,
        readonly=True,
    )
    code = fields.Char(
        string='Código',
        related='entry_type_id.code',
        store=True,
        readonly=True,
        index=True,
    )
    amount = fields.Float(
        string='Monto',
        digits='Payroll',
        help=(
            'Importe recurrente del empleado. Al elegir el tipo de entrada se propone el monto '
            'predeterminado del catálogo, pero este valor queda independiente y puede editarse.'
        ),
    )
    percentage = fields.Float(
        string='Porcentaje (%)',
        digits='Payroll Rate',
        help=(
            'Porcentaje recurrente del empleado. Capture 20 para representar 20%. '
            'Al elegir el tipo se propone el porcentaje predeterminado del catálogo, '
            'pero este valor queda independiente y puede editarse.'
        ),
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        index=True,
        help='Solo las entradas activas participan en los cálculos de nómina.',
    )

    @api.onchange('entry_type_id')
    def _onchange_entry_type_id(self):
        for line in self:
            if line.entry_type_id:
                line.amount = line.entry_type_id.default_amount
                line.percentage = line.entry_type_id.default_percentage


# Compatibilidad temporal con datos creados por la primera versión de la migración.
# No se exponen en las vistas nuevas ni deben utilizarse para nuevas capturas.
class LegacyOtherEntryType(models.Model):
    _name = 'otras.entradas.tipo'
    _description = 'Tipo de otras entradas de nómina (compatibilidad)'
    _order = 'code, name'

    name = fields.Char(string='Tipo de entrada', required=True, translate=True)
    code = fields.Char(string='Código', required=True, index=True)

    _code_unique = models.Constraint(
        'UNIQUE(code)',
        'El código del tipo de entrada debe ser único.',
    )


class LegacyOtherEmployeeEntry(models.Model):
    _name = 'otras.entradas.empleados'
    _description = 'Otras entradas del empleado (compatibilidad)'
    _order = 'form_id, estado, codigo, id'
    _rec_name = 'descripcion'

    form_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True,
    )
    monto = fields.Float(string='Monto', digits='Payroll')
    descripcion = fields.Char(string='Descripción')
    codigo = fields.Char(string='Código', index=True)
    porcentaje = fields.Float(string='Porcentaje', digits='Payroll Rate')
    estado = fields.Selection(
        selection=[('activo', 'Activo'), ('inactivo', 'Inactivo')],
        string='Estado',
        required=True,
        default='activo',
        index=True,
    )
    tipo_entrada_id = fields.Many2one(
        'otras.entradas.tipo',
        string='Tipo de entrada',
        required=True,
        index=True,
        ondelete='restrict',
    )
