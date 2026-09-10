# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.fields import Command, Domain


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        # Inicializar el dominio existente como un objeto Domain
        domain = Domain(domain or [])
        ctx = self._context

        if ctx.get('has_deputy_groups'):
            # La lógica para obtener user_ids sigue siendo la misma
            group_ids = ctx['has_deputy_groups'][0][2]
            if group_ids:
                # Usar SQL directamente si es necesario, aunque es mejor usar ORM si es posible
                # En este caso, el SQL es una forma válida de obtener los UIDs eficientemente.
                # Asegúrate de que `group_ids` no esté vacío antes de la ejecución SQL.
                if not group_ids:
                     # Si no hay grupos válidos, forzamos un dominio que no devuelva resultados si es necesario.
                     user_ids = []
                else:
                    group_ids += [-1] # ensure it's not an empty tuple for the SQL IN clause
                    sql = """
                        SELECT uid FROM res_groups_users_rel WHERE gid IN %s
                    """
                    self._cr.execute(sql, (tuple(group_ids),))
                    user_ids = [x[0] for x in self._cr.fetchall()]
                
                # Combinar el nuevo dominio con el dominio existente
                # Usamos el operador de intersección '&' para combinar dominios.
                domain &= Domain('id', 'in', user_ids)
        
        # Llamar al método super con la nueva firma y el objeto Domain
        # La llamada a super() en Odoo 19 ya no espera 'args'.
        return super().name_search(name, domain, operator, limit)