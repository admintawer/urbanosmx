# -*- coding: utf-8 -*-

from odoo import fields, models, _


class RailImssRetroactiveHireWizard(models.TransientModel):
    _name = 'rail.imss.retroactive.hire.wizard'
    _description = 'Reconstrucción retroactiva de altas IMSS'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        domain="[('company_id', '=', company_id)]",
        help='Déjelo vacío para procesar todos los empleados de la compañía.',
    )
    include_inactive = fields.Boolean(
        string='Incluir empleados archivados',
        default=True,
        help='Útil para migraciones históricas y empleados que ya causaron baja.',
    )
    date_from = fields.Date(
        string='Alta desde',
        help='Filtra por la fecha inicial del primer contrato/versión laboral.',
    )
    date_to = fields.Date(
        string='Alta hasta',
        help='Filtra por la fecha inicial del primer contrato/versión laboral.',
    )

    def action_generate(self):
        self.ensure_one()
        result = self.env['rail.imss.incidence'].rail_backfill_retroactive_hires(
            company_ids=self.company_id.ids,
            employee_ids=self.employee_ids.ids,
            include_inactive=self.include_inactive,
            date_from=self.date_from,
            date_to=self.date_to,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Altas IMSS retroactivas'),
                'message': _(
                    'Empleados revisados: %(reviewed)s. Altas creadas: %(created)s. '
                    'Altas ya existentes: %(existing)s. Sin fecha de inicio: %(missing_date)s. '
                    'Confirmadas: %(confirmed)s. En borrador por datos faltantes: %(draft)s.'
                ) % result,
                'type': 'success',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
