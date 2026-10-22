# -*- coding: utf-8 -*-

'''
Create Date:2017��9��1��

Author     :Administrator
'''
import datetime
import dateutil
import logging
import os
import time
import pdb
import logging
import odoo.tools
_logger = logging.getLogger(__name__)

from pytz import timezone

import odoo
from odoo import api, fields, models, tools, _
from odoo.exceptions import MissingError, UserError, ValidationError

class ClearDataModel(models.Model):
    _name='clear.data.model'
    
    name=fields.Char(string="Model group")
    description=fields.Text(string="Description")
    internal_model_list=fields.Text(string='Always clear',description="Model in this list do not need installed. style like this:[string,string,...]")
    model_clear_ids=fields.Many2many("ir.model",'clear_data_ir_model_rel','group_id','model_id',domain=[('model','not in',['clear.data.model'])])
    auto_clear_ir_sequence=fields.Boolean(string="Auto clear ir sequence",default=True)
    company_ids = fields.Many2many('res.company')

    def action_do_clear(self):
        self.ensure_one()
        self._do_clear_internal_model()
        self._do_clear_model_relation()
        
        if self.auto_clear_ir_sequence:
            self._do_clear_ir_sequence()
        return True

    def _do_clear_model_relation(self):
        
        self.ensure_one()
        
        for model_id in self.model_clear_ids:            
            if model_id:
               self._do_clear_by_model_name(model_id.model)

    def _do_clear_internal_model(self):
        
        self.ensure_one()
        
        if not self.internal_model_list:
            return True
        
        model_list=[]
        
        try:
            model_list=eval(self.internal_model_list)
            if type(model_list)!=list:
                raise UserError('Always clear model list format is incorrect!')
        except:
            raise UserError('Always clear model list format is incorrect!')
        
        if all(model_list):
            
            for model_name in model_list:
                self._do_clear_by_model_name(model_name)
                
        return True

    def _do_clear_by_model_name(self,model_name):
        self.ensure_one()
        model_obj=self.env.get(model_name,None)
        if model_obj==None or not odoo.tools.sql.table_exists(self._cr, model_obj._table):
            return
        # Check if the 'company_id' field exists in the model
        if 'company_id' in model_obj._fields and not model_obj._fields['company_id'].readonly and self.company_ids:
            companies = ','.join([str(x) for x in self.company_ids.ids])

            # Construct the SQL query with a WHERE condition
            sql = "DELETE FROM %s WHERE company_id in (%s)" % (model_obj._table, companies)
            
            # Execute the SQL query with a placeholder for the company_id value
            self._cr.execute(sql)
        elif not self.company_ids:       
            sql="delete from %s" % model_obj._table
            self._cr.execute(sql)
        elif self.company_ids and 'company_id' not in model_obj._fields:
            raise ValidationError("Estas tratando de borrar registros por compania pero dichos registros son para todo el ambiente")

    def _do_clear_ir_sequence(self):
        cr = self._cr

        model_codes = self.model_clear_ids.mapped('model')

        if not model_codes:
            _logger.info("No se seleccionaron modelos para limpiar. No se reiniciará ninguna secuencia.")
            return
        
        seq_list = self.env['ir.sequence'].search([
            ('implementation', '=', 'standard'),
            ('code', 'in', model_codes)
        ])

        if not seq_list:
            _logger.info("No se encontraron secuencias para reiniciar.")
            return

        for seq in seq_list:
            _logger.info("Reiniciando secuencia: %s (code=%s, prefix=%s)", seq.name, seq.code, seq.prefix)

            cr.execute("ALTER SEQUENCE ir_sequence_%03d RESTART WITH 1" % seq.id)

            for seq_range in seq.date_range_ids:
                cr.execute("ALTER SEQUENCE ir_sequence_%03d_%03d RESTART WITH 1" % (seq.id, seq_range.id))

class IrModel(models.Model):
    _inherit = 'ir.model'
    
    sequence = fields.Integer('Sequence', help="Used to order models.", default=1)
    
    