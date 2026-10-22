# -*- coding: utf-8 -*-

from odoo import models, _


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    def action_register_departure(self):
        departure_data = []
        for employee in self.employee_ids:
            version = employee._get_version(self.departure_date)
            departure_data.append((employee, version))

        action = super().action_register_departure()

        incidence_model = self.env['rail.imss.incidence']
        for employee, version in departure_data:
            if not version:
                continue
            incidence_model.rail_get_or_create_event(
                employee=employee,
                version=version,
                event_date=self.departure_date,
                incidence_type='leave',
                origin='departure',
                values={
                    'old_wage': version.wage,
                    'new_wage': 0.0,
                    'old_sbc': version.rail_fixed_sbc,
                    'new_sbc': 0.0,
                    'note': _(
                        'Baja generada desde el asistente de salida. Motivo: %s'
                    ) % (self.departure_reason_id.display_name or ''),
                },
                automatic=True,
            )
        return action
