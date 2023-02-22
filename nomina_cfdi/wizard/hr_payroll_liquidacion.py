# -*- coding: utf-8 -*-

import struct
from odoo import models, api, fields, _
from datetime import datetime
from datetime import date

import time
from odoo.exceptions import Warning
import logging
_logger = logging.getLogger(__name__)

class GeneraLiquidaciones(models.TransientModel):
    _name = 'calculo.liquidaciones'
    _description = 'GeneraLiquidaciones'

    fecha_inicio = fields.Date(string='Fecha inicio último periodo')
    fecha_liquidacion = fields.Date(string='Fecha liquidacion')
    employee_id =fields.Many2one("hr.employee",'Employee')
    dias_base = fields.Float('Días base', default='90')
    dias_x_ano = fields.Float('Días por cada año trabajado', default='20')
    dias_totales = fields.Float('Total de días', store=True)
    indemnizacion = fields.Boolean("Pagar indemnización")
    antiguedad = fields.Boolean("Pagar antiguedad")
    dias_pendientes_pagar = fields.Float('Días de nómina a pagar', store=True)
    dias_vacaciones = fields.Float('Días de vacaciones')
    dias_aguinaldo = fields.Float('Días aguinaldo')
    dias_prima_vac = fields.Float('Días prima vacacional')
    fondo_ahorro = fields.Float('Fondo ahorro', compute="get_fondo_ahorro", store=True)
    pago_separacion = fields.Float("Pago por separación")
    contract_id = fields.Many2one('hr.contract', string='Contrato')
    antiguedad_anos = fields.Float('Antiguedad', store=True)

    monto_prima_antiguedad = fields.Float('Prima antiguedad', store=True)
    monto_indemnizacion = fields.Float('Indemnizacion', store=True)
    tipo_de_baja = fields.Selection([('01','Separación voluntaria'),
                                      ('02','Baja')], string='Tipo de baja')
    sueldo_calculo = fields.Selection([('01','Sueldo diario'),
                                      ('02','Sueldo diario integrado')], string='Sueldo para cálculos')
    sueldo_calculo_monto  = fields.Float('Sueldo calculo monto')
    tope_prima = fields.Selection([('01','Sueldo diario'),
                                      ('02','UMA')], string='Para calculo topado usar')
    tope_prima_monto  = fields.Float('Tope prima monto')
    estructura  = fields.Many2one('hr.payroll.structure', string='Estructura ordinaria')
    prima_vac = fields.Float('Días aguinaldo prima vacacional')

    def calculo_create(self):
        employee = self.employee_id
        if not employee:
            raise Warning("Seleccione primero al empleado.")
        payslip_batch_nm = 'Liquidacion ' +employee.name
        date_from = self.fecha_inicio
        date_to = self.fecha_liquidacion
        batch = self.env['hr.payslip.run'].create({
            'name' : payslip_batch_nm,
            'date_start': date_from,
            'date_end': date_to,
            'periodicidad_pago': self.contract_id.periodicidad_pago,
            'no_nomina': '1',
            'tipo_nomina': 'E',
            'fecha_pago' : date_to,
            })
        # batch
        #payslip_obj = self.env['hr.payslip']
        #payslip_onchange_vals = payslip_obj.onchange_employee_id(date_from, date_to, employee_id=employee.id)
        #Creación de nomina ordinaria
        #payslip_vals = {**payslip_onchange_vals.get('value',{})} #TO copy dict to new dict. 
        
        structure = self.estructura #self.env['hr.payroll.structure'].search([('name','=','Liquidación - Ordinario')], limit=1)
        #if structure: 
        #    payslip_vals['struct_id'] = structure.id
        
        contract_id = self.contract_id.id
        #if not contract_id:
        #    contract_id = payslip_vals.get('contract_id')
        #else:
        #    payslip_vals['contract_id'] = contract_id 
        
        if not contract_id:
            contract_id = employee.contract_id.id
        if not contract_id:
            raise Warning("No se encontró contrato para %s en el periodo de tiempo."%(employee.name))
        
        worked_days = [(5,0,0)]
        pvc_type = self.env['hr.work.entry.type'].search([('code','=','PVC')],limit=1)
        vac_type = self.env['hr.work.entry.type'].search([('code','=','VAC')],limit=1)  
        agui_type = self.env['hr.work.entry.type'].search([('code','=','AGUI')],limit=1)
        worked_days.append((0,0,{'work_entry_type_id': agui_type.id, 'name' :'Dias aguinaldo', 'code' : 'AGUI', 'number_of_days': self.dias_aguinaldo}))
        worked_days.append((0,0,{'work_entry_type_id': vac_type.id, 'name' :'Dias vacaciones', 'code' : 'VAC', 'number_of_days': self.dias_vacaciones}))
        worked_days.append((0,0,{'work_entry_type_id': pvc_type.id, 'name' :'Prima vacacional', 'code' : 'PVC', 'number_of_days': self.dias_prima_vac}))
        worked_days.append((0,0,{'work_entry_type_id': 1, 'name' :'Dias a pagar', 'code' : 'WORK100', 'number_of_days': self.dias_pendientes_pagar}))
        
        pfa_type = self.env['hr.payslip.input.type'].search([('code','=','PFA')], limit=1)
        inputs = [(5,0,0)]
        input = (0,0, {'input_type_id': pfa_type.id, 'name':'[PFA] Fondo ahorro', 'amount': self.fondo_ahorro})
        inputs.append(input)
        journal = self.env['account.journal'].search([('code','=','Nomin')], limit=1)
        payslips = self.env['hr.payslip']
        Payslip = self.env['hr.payslip']
        default_values = Payslip.default_get(Payslip.fields_get())
        payslip_vals = []
        values = dict(default_values, **{
            'name': _('New Payslip'),
            'employee_id' : employee.id,
            'tipo_nomina' : 'O',
            'payslip_run_id' : batch.id,
            'date_from': date_from,
            'date_to': date_to,
            'contract_id' : contract_id,
            'struct_id': structure.id,
            'journal_id': journal.id,
            'no_nomina': '1',
            'fecha_pago' : date_to,
            'mes': '{:02d}'.format(date_to.month),
            'dias_pagar': self.dias_pendientes_pagar,
            'imss_dias': self.dias_pendientes_pagar,
            'nom_liquidacion': True,
            'worked_days_line_ids': worked_days,
            'input_line_ids': inputs,
            })
        payslip_vals.append(values)

        payslips = Payslip.with_context(tracking_disable=True).create(payslip_vals)
        payslips._compute_name()
        for r in payslips:
            r.compute_sheet()
        
        #Creación de nomina extraordinaria
        if self.tipo_de_baja == '02':
            #payslip_vals2 = {**payslip_onchange_vals.get('value',{})}
            structure2 = self.env['hr.payroll.structure'].search([('name','=','Liquidación - indemnizacion/finiquito')], limit=1)
            #if structure: 
            #    payslip_vals2['struct_id'] = structure.id
            pda_type = self.env['hr.payslip.input.type'].search([('code','=','PDA')], limit=1)
            ind_type = self.env['hr.payslip.input.type'].search([('code','=','IND')], limit=1)
            pps_type = self.env['hr.payslip.input.type'].search([('code','=','PPS')], limit=1)
            other_inputs = []
            other_inputs.append((0,0,{'input_type_id': pda_type.id, 'name' :'[PDA] Prima antiguedad', 'amount': self.monto_prima_antiguedad}))
            other_inputs.append((0,0,{'input_type_id': ind_type.id, 'name' :'[IND] Indemnizacion', 'amount': self.monto_indemnizacion}))
            other_inputs.append((0,0,{'input_type_id': pps_type.id, 'name' :'[PPS] Pago por separacion', 'amount': self.pago_separacion}))
            worked_days2 = []
            worked_days2.append((0,0,{'work_entry_type_id': 1,'name' :'Dias a pagar', 'code' : 'WORK100', 'number_of_days': 0}))

            payslip_vals2 = []
            values2 = dict(default_values, **{
                'name': _('New Payslip'),
                'employee_id' : employee.id,
                'tipo_nomina' : 'E',
                'payslip_run_id' : batch.id,
                'date_from': date_from,
                'date_to': date_to,
                'contract_id' : contract_id,
                'struct_id': structure2.id,
                'journal_id': journal.id,
                #'no_nomina': '1',
                'fecha_pago' : date_to,
                'worked_days_line_ids': worked_days,
                'input_line_ids': inputs,
                })
            payslip_vals2.append(values2)
            payslips2 = Payslip.with_context(tracking_disable=True).create(payslip_vals)
            payslips2._compute_name()
            for r2 in payslips2:
                r2.compute_sheet()
            
        return
    
    def calculo_liquidacion(self):
        if self.employee_id and self.contract_id:
            #cálculo de conceptos de nómina extraordinaria
            date_start = self.contract_id.date_start
            last_day = self.fecha_liquidacion
            diff_date = last_day - date_start 
            self.antiguedad_anos = diff_date.days /365.0
          
            if self.sueldo_calculo == '01':
                self.sueldo_calculo_monto = self.contract_id.sueldo_diario
            else:
                self.sueldo_calculo_monto = self.contract_id.calculate_sueldo_diario_integrado()

            #calculo de dias a indemnizar
            if self.indemnizacion:
                self.dias_totales = self.antiguedad_anos * self.dias_x_ano + self.dias_base
            else:
                self.dias_totales = 0
            self.monto_indemnizacion = self.dias_totales * self.sueldo_calculo_monto

            # calculo prima antiguedad: 12 días de salario por cada año de servicio.
            if self.antiguedad:
                tope_prima_antiguedad = 2 * self.contract_id.tablas_cfdi_id.salario_minimo
                _logger.info('dias tope_prima_antiguedad %s', tope_prima_antiguedad)
                if self.tope_prima == '01':
                    self.tope_prima_monto = self.contract_id.tablas_cfdi_id.salario_minimo
                else:
                    self.tope_prima_monto = self.contract_id.tablas_cfdi_id.uma

                if self.sueldo_calculo_monto > tope_prima_antiguedad:
                    _logger.info('mayor')
                    self.monto_prima_antiguedad = round(self.antiguedad_anos) * 12 * self.tope_prima_monto * 2
                else:
                    _logger.info('menor')
                    self.monto_prima_antiguedad = round(self.antiguedad_anos) * 12 * self.sueldo_calculo_monto
            else:
                self.monto_prima_antiguedad = 0

            #cálculo de conceptos de nómina ordinaria
            #dias pendientes a pagar en ultima nomina
            delta_dias  = self.fecha_liquidacion - self.fecha_inicio
            self.dias_pendientes_pagar = delta_dias.days + 1

            #Dias de aguinaldo
            year_date_start = self.contract_id.date_start.year
            first_day_date = datetime(date.today().year, 1, 1).date()
            if year_date_start < date.today().year:
                delta1 = self.fecha_liquidacion - first_day_date # datetime.strptime(first_day_date,"%Y-%m-%d")
                self.dias_aguinaldo = delta1.days + 1 
            else:
                delta2 = self.fecha_liquidacion - self.contract_id.date_start
                self.dias_aguinaldo = delta2.days + 1

            if self.contract_id.tablas_cfdi_id:
                line = self.env['tablas.antiguedades.line'].search([('form_id','=',self.contract_id.tablas_cfdi_id.id),('antiguedad','<=',self.antiguedad_anos+1)],order='antiguedad desc',limit=1)
                if line:
                    dias_aguinaldo2 = line.aguinaldo
                    self.dias_aguinaldo = (dias_aguinaldo2*self.dias_aguinaldo)/365.0
                    _logger.info('dias %s, dias aguinaldo %s,', self.dias_aguinaldo, dias_aguinaldo2)

            #dias de vacaciones
            vac_pagada = False
            dias_vac = 0
            if date_start:
                date_start = date_start.replace(last_day.year)
                _logger.info('last_day %s, date_start %s', last_day, date_start) 
                if last_day <= date_start:
                    #_logger.info('last_day <= date_start') 
                    #_logger.info('self.antiguedad_ano %s', self.antiguedad_anos) 
                    date_start = date_start.replace(last_day.year-1)
                    tablas_cfdi_lines = self.contract_id.tablas_cfdi_id.tabla_antiguedades.filtered(lambda x: x.antiguedad <= self.antiguedad_anos+1).sorted(key=lambda x:x.antiguedad, reverse=True)
                    if not tablas_cfdi_lines: 
                        return
                    tablas_cfdi_line = tablas_cfdi_lines[0]
                    #_logger.info('dias vacaciones correspondientes %s', tablas_cfdi_line.vacaciones) 
                    #_logger.info('dias a pagar %s', (last_day - date_start).days +1) 
                    self.dias_vacaciones = ((last_day - date_start).days + 1)  / 365.0 * tablas_cfdi_line.vacaciones
                    self.prima_vac = tablas_cfdi_line.prima_vac
                else:
                    #_logger.info('last_day > date_start') 
                    #_logger.info('self.antiguedad_ano %s', self.antiguedad_anos)
                    tablas_cfdi_lines = self.contract_id.tablas_cfdi_id.tabla_antiguedades.filtered(lambda x: x.antiguedad <= self.antiguedad_anos+1).sorted(key=lambda x:x.antiguedad, reverse=True)
                    if not tablas_cfdi_lines: 
                        return
                    tablas_cfdi_line = tablas_cfdi_lines[0]
                    #_logger.info('dias vacaciones correspondientes %s', tablas_cfdi_line.vacaciones) 
                    #_logger.info('dias a pagar %s', (last_day - date_start).days +1) 
                    self.dias_vacaciones = ((last_day - date_start).days + 1) / 365.0 * tablas_cfdi_line.vacaciones
                    self.prima_vac = tablas_cfdi_line.prima_vac


            #dias de vacaciones adicionales entregados y no pagados
            if self.contract_id.tipo_prima_vacacional == '02':
                ano_buscar = 0
                if last_day <= date_start:
                    ano_buscar = last_day.year -1
                else:
                    ano_buscar = last_day.year
                for lineas_vac in self.contract_id.tabla_vacaciones:
                    if lineas_vac.ano == str(ano_buscar):
                        self.dias_vacaciones += lineas_vac.dias

            #fondo de ahorro (si hay)
            self.fondo_ahorro = self.get_fondo_ahorro()

            #prima vacacional liquidacion
            self.dias_prima_vac = self.dias_vacaciones * self.prima_vac / 100.0
        return {
            'name': _('Calculo Liquidaciones'),
            'view_mode': 'form',
            'res_model': 'calculo.liquidaciones',
            'res_id': 	self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


    def genera_nominas(self):
        dias_vacaciones = 0

    def get_fondo_ahorro(self):
        total = 0
        if self.employee_id and self.contract_id.tablas_cfdi_id:
            year_date_start = self.contract_id.date_start.year
            first_day_date = datetime(date.today().year, 1, 1)
            if year_date_start < date.today().year:
                date_start = first_day_date
            else:
                date_start = self.contract_id.date_start
            date_end = self.fecha_liquidacion

            domain=[('state','=', 'done')]
            if date_start:
                domain.append(('date_from','>=',date_start))
            if date_end:
                domain.append(('date_to','<=',date_end))
            domain.append(('employee_id','=',self.employee_id.id))
            rules = self.env['hr.salary.rule'].search([('code', '=', 'D067')])
            payslips = self.env['hr.payslip'].search(domain)
            payslip_lines = payslips.mapped('line_ids').filtered(lambda x: x.salary_rule_id.id in rules.ids)
            employees = {}
            for line in payslip_lines:
                if line.slip_id.employee_id not in employees:
                    employees[line.slip_id.employee_id] = {line.slip_id: []}
                if line.slip_id not in employees[line.slip_id.employee_id]:
                    employees[line.slip_id.employee_id].update({line.slip_id: []})
                employees[line.slip_id.employee_id][line.slip_id].append(line)

            for employee, payslips in employees.items():
                for payslip,lines in payslips.items():
                    for line in lines:
                        total += line.total
        return total

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id and self.fecha_inicio and self.fecha_liquidacion:
           contratos = self.get_contract(self.employee_id, self.fecha_inicio, self.fecha_liquidacion)
           values = {
                  'contract_id': contratos[0],
              }
           self.update(values)

    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        @param employee: recordset of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        # a contract is valid if it ends between the given dates
        clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]
        # OR if it starts between the given dates
        clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]
        # OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]
        clause_final = [('employee_id', '=', employee.id), ('state', '=', 'open'), '|', '|'] + clause_1 + clause_2 + clause_3
        return self.env['hr.contract'].search(clause_final).ids