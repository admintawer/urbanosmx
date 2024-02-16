# -*- coding: utf-8 -*-

from odoo import models, fields

class TipoDeduccion(models.Model):
    _name = 'nomina.deduccion'
    _rec_name = "descripcion"
    _description = 'TipoDeduccion'

    clave = fields.Char(string='Clave')
    descripcion = fields.Char(string='Descripción')

class TipoPercepcion(models.Model):
    _name = 'nomina.percepcion'
    _rec_name = "descripcion"
    _description = 'TipoPercepcion'

    clave = fields.Char(string='Clave')
    descripcion = fields.Char(string='Descripción')

class TipoOtroPago(models.Model):
    _name = 'nomina.otropago'
    _rec_name = "descripcion"
    _description = 'TipoOtroPago'

    clave = fields.Char(string='Clave')
    descripcion = fields.Char(string='Descripción')

class TipoRegimen(models.Model):
    _name = 'nomina.tipo.regimen'
    _rec_name = 'descripcion'
    _description = 'TipoRegimen'

    clave = fields.Char(string='Clave')
    descripcion = fields.Char(string="Descripcion")

class TipoContrato(models.Model):
    _name = 'nomina.tipo.contrato'
    _rec_name = 'descripcion'
    _description = 'TipoContrato'

    clave = fields.Char(string="Clave")
    descripcion = fields.Char(string="Descripcion")
    regimen_ids = fields.Many2many('nomina.tipo.regimen')