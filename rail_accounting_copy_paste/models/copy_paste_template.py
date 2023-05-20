# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging, json
from datetime import datetime
_logger = logging.getLogger(__name__)

class CopyPasteTemplate(models.Model):
    _name = 'copy.paste.template'
    _description = 'Accounting copy paste template'

    name = fields.Char('Name')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    source_company_ids = fields.Many2many('res.company', column1='template_id',
                                    column2='company_id')

    sale_journal_id = fields.Many2one('account.journal', domain=[('type','=','general')])
    purchase_journal_id = fields.Many2one('account.journal', domain=[('type','=','general')]) 
    bank_journal_id = fields.Many2one('account.journal', domain=[('type','=','general')])
    cash_journal_id = fields.Many2one('account.journal', domain=[('type','=','general')])
    general_journal_id = fields.Many2one('account.journal', domain=[('type','=','general')])
    error = fields.Text("Error")

    date_start = fields.Date('Initial day for syncing')
    
    def _get_account_moves_to_matrix(self):
        move_object = self.env['account.move']
        company_id = self.company_id
        date_end = datetime.today().date()
        for c in self.source_company_ids:
            domain = [
                    ('company_id','=', c.id),
                    ('not_sync','=', False),
                    ('synced','=',False),
                    ('state','=','posted'),
                    ('date','>=',self.date_start),
                    ('date','<=', date_end)]
            
            journal_types = []
            if self.sale_journal_id:
                journal_types.append('sale')
            if self.purchase_journal_id:
                journal_types.append('purchase')
            if self.bank_journal_id:
                journal_types.append('bank')
            if self.cash_journal_id:
                journal_types.append('cash')
            if self.general_journal_id:
                journal_types.append('general')

            domain.append(('journal_id.type','in', journal_types))
                
            moves = self.env['account.move'].sudo().search(domain)

            if moves:
                for m in moves:
                    if m.journal_id.type == 'sale':
                        journal_id = self.sale_journal_id
                    elif m.journal_id.type == 'purchase':
                        journal_id = self.purchase_journal_id
                    elif m.journal_id.type == 'bank':
                        journal_id = self.bank_journal_id
                    elif m.journal_id.type == 'cash':
                        journal_id = self.cash_journal_id
                    elif m.journal_id.type == 'general':
                        journal_id = self.general_journal_id

                    move_dict = {
                        'ref': c.name + ' | ' + m.journal_id.name + ' | ' + m.name,
                        'journal_id': journal_id.id,
                        'date': m.date,
                        'synced': True,
                        'from_sync': True,
                        'company_id': company_id.id,
                        'source_company_id': m.company_id.id
                    }
                    m_lines = []
                    for ml in m.line_ids:
                        matrix_account = self.env['account.account'].sudo().search([('code','=',ml.account_id.code),('company_id','=', company_id.id)])
                        dist_dict = {}
                        for al in ml.analytic_line_ids:                            
                            matrix_analytic = self.env['account.analytic.account'].sudo().search([('name','=',al.account_id.name),('company_id','=', company_id.id)], limit=1)
                            if ml.debit == 0:
                                dist_total = ml.credit
                            else:
                                dist_total = ml.debit
                            
                            dist_percentage = abs(round((al.amount / dist_total) * 100, ml.analytic_precision))
                            dist_dict.update({
                                str(matrix_analytic.id): dist_percentage,
                            })
                        m_line = (0,0, {
                            'display_type': ml.display_type,
                            'name': ml.name,
                            'partner_id': ml.partner_id.id,
                            'account_id': matrix_account.id,
                            'journal_id': journal_id.id,
                            'amount_currency': ml.amount_currency,
                            'currency_id': ml.currency_id.id,
                            'date': ml.date,
                            'debit': ml.debit,
                            'credit': ml.credit,
                            'company_id': company_id.id,
                            'analytic_distribution': dist_dict,
                        })
                        m_lines.append(m_line)
                    move_dict['line_ids'] = m_lines
                    move = move_object.create(move_dict)
                    move._post()
                    m.sudo().write({'matrix_ref': move.name, 'synced': True,})
                    
    def action_send_email(self):
        mail_template = self.env.ref('rail_accounting_copy_paste.error_sync_email_template')
        mail_template.send_mail(self.id, force_send=True)

    def run_from_cron(self):
        templates = self.env['copy.paste.template'].search([])
        if templates:
            for t in templates:
                t.compare_accounts()

    def compare_accounts(self):
        source_accounts = self.env['account.account'].search([('company_id','=', self.company_id.id)])
        source_analytic = self.env['account.analytic.account'].search([('company_id','=', self.company_id.id)])
        missing_accounts = False
        missing_analytic = False
        #Cuentas contables
        if source_accounts:
            sa_list = []
            for a in source_accounts:
                sa_list.append(a.code)
            missing_accounts = self.env['account.account'].sudo().search([('company_id','in', self.source_company_ids.ids),('code','not in', sa_list)])
        if source_analytic:
            sac_list = []
            for ac in source_analytic:
                sac_list.append(ac.name)
            missing_analytic = self.env['account.analytic.account'].sudo().search([('company_id','in', self.source_company_ids.ids),('name','not in', sac_list)])
        if missing_accounts or missing_analytic:
            ma_list = []
            for r in missing_accounts:
                ma_list.append(r.display_name)
            for p in missing_analytic:
                ma_list.append(p.display_name)
            body_error = 'No se puede continuar con el proceso, las siguientes cuentas no se encuentran creadas en: '+ self.company_id.display_name + '\n' \
                            + ', '.join(ma_list)
            self.error = body_error
            self.action_send_email()
            raise ValidationError(body_error)
        else:
            try:
                self._get_account_moves_to_matrix()
                return {
                    'effect':{
                        'fadeout': 'slow',
                        'message': 'El proceso de sincronizacion ha finalizado satisfactoriamente',
                        'type': 'rainbow_man',
                    }
                }
            except Exception as e:
                raise ValidationError("Algo a salido mal con  la sincronizacion por favor contacta a soporte \n"\
                                      + str(e))       
            

            
