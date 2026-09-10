# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config, SQL
from odoo.tools.safe_eval import safe_eval, datetime
from odoo.fields import Domain
from pytz import timezone, UTC

# from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.addons.advanced_web_domain_widget.models.domain_prepare import compute_domain
import logging

_logger = logging.getLogger(__name__)

def eval_custom_domain(self, domain_str):
        eval_context = {
            'datetime': datetime,
            'relativedelta': relativedelta,
            'context_today': lambda: fields.Date.context_today(self),
        }
        domain_list = safe_eval(domain_str, eval_context)
        return Domain(domain_list)

class ir_rule(models.Model):
    _inherit = 'ir.rule'

    

    @api.model
    @tools.conditional(
        'xml' not in config['dev_mode'],
        tools.ormcache('self.env.uid', 'self.env.su', 'model_name', 'mode',
                       'tuple(self._compute_domain_context_values())'),
    )
    def _compute_domain(self, model_name, mode="read"):
        res = super(ir_rule, self)._compute_domain(model_name, mode)

        if self.env.context.get('call_by_advance'):
            return res

        read_value = True
        self.env.cr.execute(SQL("SELECT state FROM ir_module_module WHERE name='simplify_access_management'"))
        data = self.env.cr.fetchone() or False

        self.env.cr.execute(SQL("SELECT id FROM ir_module_module WHERE state IN ('to upgrade', 'to remove', 'to install')"))
        all_data = self.env.cr.fetchone() or False

        if data and data[0] != 'installed':
            read_value = False
        model_list = ['mail.activity', 'res.users.log', 'res.users', 'mail.channel', 'mail.alias', 'bus.presence',
                      'res.lang']

        # if self.env.user.id and read_value and not all_data:
            # if model_name not in model_list:
                # self._cr.execute(SQL("""SELECT am.id FROM access_management as am
                #                     WHERE active='t' AND readonly = True AND am.id 
                #                     IN (SELECT au.access_management_id 
                #                         FROM access_management_users_rel_ah as au 
                #                         WHERE user_id = %s AND am.id 
                #                         IN (SELECT ac.access_management_id
                #                             FROM access_management_comapnay_rel as ac)) """ % (self.env.user.id))) 
                
                # a = self._cr.fetchall()
                # a = self.env['access.management'].sudo().browse(
                #             row[0] for row in self._cr.fetchall())
                # if a:
                #     a -= a.filtered(lambda x: x.is_apply_on_without_company == False and self.env.company.id not in x.company_ids.ids)
                #     if bool(a):
                #         if mode != 'read' and model_name not in ['mail.channel.partner']:
                #             raise UserError(
                #                 _('%s is a read-only user. So you can not make any changes in the system!') % self.env.user.name)
        value = self.env.cr.execute(SQL(
            """SELECT value from ir_config_parameter where key='uninstall_simplify_access_management' """))
        value = self.env.cr.fetchone()
        if not value:
            self.env.cr.execute(SQL("""SELECT state FROM ir_module_module WHERE name='simplify_access_management'"""))
            value = self.env.cr.fetchone()
            value = value and value[0] or False
            if model_name and model_name in self.env and value == 'installed':

                query = SQL("SELECT id FROM ir_model WHERE model=%s", (model_name,))
                self.env.cr.execute(query)

                model_numeric_id = self.env.cr.fetchone()
                model_numeric_id = model_numeric_id and model_numeric_id[0] or False
                if model_numeric_id and isinstance(model_numeric_id, int) and self.env.user:
                    try:
                        query = SQL('''
                                    SELECT dm.id
                                    FROM access_domain_ah dm
                                    WHERE dm.model_id = %s 
                                    AND dm.apply_domain 
                                    AND dm.access_management_id IN (
                                        SELECT am.id 
                                        FROM access_management am 
                                        WHERE active = 't' 
                                        AND am.id IN (
                                            SELECT amusr.access_management_id
                                            FROM access_management_users_rel_ah amusr
                                            WHERE amusr.user_id = %s
                                        )
                                    )
                                ''' % (model_numeric_id, self.env.user.id))

                        self.env.cr.execute(query)

                        access_domain_ah_ids = self.env['access.domain.ah'].sudo().browse(
                            row[0] for row in self.env.cr.fetchall())
                        
                        access_domain_ah_ids -= access_domain_ah_ids.filtered(
                            lambda x: x.access_management_id.is_apply_on_without_company == False 
                            and self.env.company.id not in x.access_management_id.company_ids.ids)
                    except Exception as e:
                        _logger.error("Error fetching access_domain_ah for model=%s: %s", model_name, str(e))
                        access_domain_ah_ids = False
                    
                    if access_domain_ah_ids:
                        domain_list = []
                        if model_name == 'res.partner':
                            self.env.cr.execute(SQL("""SELECT partner_id FROM res_users"""))
                            partner_ids = [row[0] for row in self.env.cr.fetchall()]
                            domain_list = ['|', ('id', 'in', partner_ids)]
                        
                        eval_context = self._eval_context()
                        # safe_eval(self.domain, {
                        #     'datetime': datetime,
                        #     'context_today': datetime.datetime.now,
                        # })
                        # eval_context = self.env['ir.filters']._get_eval_domain()
                        # eval_context.update({
                        #     'datetime': datetime,
                        #     'context_today': datetime.datetime.now,
                        # })
                        length = len(access_domain_ah_ids.sudo()) if access_domain_ah_ids.sudo() else 0
                        
                        for access in access_domain_ah_ids.sudo():
                            # dom = safe_eval(access.domain, eval_context) if access.domain else []
                            # dom = Domain(safe_eval(access.domain, eval_context)) if access.domain else []
                            # dom = Domain(safe_eval(access.domain, {
                            #         'datetime': datetime,
                            #         'context_today': datetime.datetime.now,
                            #     }))
                            # domain = eval_custom_domain(self,access.domain) if access.domain else []
                            clean_domain_str = access.domain.replace('.to_utc()', '')
                            dom = safe_eval(clean_domain_str, {
                                'datetime': datetime,
                                'relativedelta': relativedelta,
                                'context_today': lambda: fields.Date.context_today(self),
                            })
                            if not dom and isinstance(dom, list):
                                if length > 1:
                                    domain_list.insert(0, '|')
                                domain_list += [('id', '!=', False)]
                                length -= 1
                            
                            if dom:
                                for dom_tuple in dom:
                                    if isinstance(dom_tuple, tuple):
                                        compute_domain(dom_tuple, model_name)
                                        # operator_value = dom_tuple[1]
                                        # domain_list.append(dom_tuple)
                                        # if operator_value == 'date_filter':
                                        #     domain_list += prepare_domain_v2(dom_tuple)
                                        domain_list.append(dom_tuple)
                                    else:
                                        domain_list.append(dom_tuple)
                                if length > 1:
                                    domain_list.insert(0, '|')
                                    length -= 1
                        
                        if domain_list:
                            _logger.debug("Final domain for model=%s: %s", model_name, domain_list)
                            return Domain(domain_list)

        _logger.debug("Returning base domain for model=%s: %s", model_name, res)
        return res
