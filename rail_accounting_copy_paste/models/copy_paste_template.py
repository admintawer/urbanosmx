# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
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

    date_start = fields.Date('Initial day for syncing')
    
    def _get_account_moves_to_matrix(self):
        move_object = self.env['account.move']
        company_id = self.company_id
        for c in self.source_company_ids:

            moves = self.env['account.move'].sudo().search([
                                                        ('company_id','=', c.id),
                                                        ('not_sync','=', False),
                                                        ('synced','=',False),
                                                        ('state','=','posted'),
                                                        ('date','>=',self.date_start)])
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
                        m_line = (0,0, {
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
                        })
                        m_lines.append(m_line)
                    move_dict['line_ids'] = m_lines
                    move = move_object.create(move_dict)
                    move._post()
                    m.sudo().write({'matrix_ref': move.name, 'synced': True,})

    def compare_accounts(self):
        source_accounts = self.env['account.account'].search([('company_id','=', self.company_id.id)])
        missing_accounts = False
        if source_accounts:
            sa_list = []
            for a in source_accounts:
                sa_list.append(a.code)
            missing_accounts = self.env['account.account'].search([('company_id','in', self.source_company_ids.ids),('code','not in', sa_list)])
        if missing_accounts:
            ma_list = []
            for r in missing_accounts:
                ma_list.append(r.display_name)
            raise ValidationError(_('Cant continue with the process, missing accounts in matrix company:' + ', '.join(ma_list)))
        else:
            self._get_account_moves_to_matrix()
            

            
