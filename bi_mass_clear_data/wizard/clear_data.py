# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class ClearData(models.TransientModel):
    _name = 'clear.data'
    _description = 'Clear Data'

    name = fields.Char(string="Clear Data",default="Clear Data")
    all_data = fields.Boolean(string="All Data",default=False)
    sale_and_transfer = fields.Boolean(string="Sales & All Transfers",default=False)
    purchase_and_transfer = fields.Boolean(string="Purchase & All Transfers",default=False)
    transfer = fields.Boolean(string="Only Transfers",default=False)

    task_timesheet = fields.Boolean(string="Only Tasks & Timesheets",default=False)
    project_task_timesheet = fields.Boolean(string="Project, Tasks & Timesheets",default=False)
    invoice_payment_journal = fields.Boolean(string="All Invoicing, Payments & Journal Entries",default=False)
    journal_entry = fields.Boolean(string="Only Journal Entries",default=False)

    customer_vendor = fields.Boolean(string="Customers & Vendors",default=False)
    all_accounting_data = fields.Boolean(string="Chart of Accounts & All Accounting Data",default=False)
    mrp_order = fields.Boolean(string="Only Manufacturing Orders",default=False)
    bom_mrp_order = fields.Boolean(string="BOM & Manufacturing Orders",default=False)

    @api.onchange('all_data')
    def onchange_all_data(self):
        for record in self:
            if record.all_data == True:
                record.write({
                    'sale_and_transfer':True,
                    'purchase_and_transfer':True,
                    'transfer':True,
                    'task_timesheet':True,
                    'project_task_timesheet':True,
                    'invoice_payment_journal':True,
                    'journal_entry':True,
                    'customer_vendor':True,
                    'all_accounting_data':True,
                    'mrp_order':True,
                    'bom_mrp_order':True,
                })
            if record.all_data == False:
                record.write({
                    'sale_and_transfer':False,
                    'purchase_and_transfer':False,
                    'transfer':False,
                    'task_timesheet':False,
                    'project_task_timesheet':False,
                    'invoice_payment_journal':False,
                    'journal_entry':False,
                    'customer_vendor':False,
                    'all_accounting_data':False,
                    'mrp_order':False,
                    'bom_mrp_order':False,
                })

    def clear_data(self):
        for record in self:
            if record.all_data:
                property_obj = self.env['ir.property'].search([])
                property_obj.unlink()
            if record.sale_and_transfer:
                sale_model = self.env['ir.model'].search([('model','=','sale.order')])
                if sale_model:
                    sale_obj = self.env['sale.order'].search([])
                    for sale in sale_obj:
                        sale.action_cancel()
                    sale_obj.with_context(force_unlink_saleorder=True).unlink()
                    picking_obj = self.env['stock.picking'].search([('picking_type_id.code','=','outgoing')])
                    for picking in picking_obj:
                        picking.mapped('move_ids')._action_cancel()
                        picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                    picking_obj.unlink()

            if record.purchase_and_transfer:
                purchase_model = self.env['ir.model'].search([('model','=','purchase.order')])
                if purchase_model:
                    purchase_obj = self.env['purchase.order'].search([])
                    for purchase in purchase_obj:
                        purchase.button_cancel()
                    purchase_obj.unlink()
                    picking_obj = self.env['stock.picking'].search([('picking_type_id.code','=','incoming')])
                    for picking in picking_obj:
                        picking.mapped('move_ids')._action_cancel()
                        picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                    picking_obj.unlink()

            if record.transfer:
                picking_model = self.env['ir.model'].search([('model','=','stock.picking')])
                if picking_model:
                    picking_obj = self.env['stock.picking'].search([])
                    for picking in picking_obj:
                        picking.mapped('move_ids')._action_cancel()
                        picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                    picking_obj.unlink()

            if record.task_timesheet:
                task_timesheet_model = self.env['ir.model'].search([('model','=','account.analytic.line')])
                if task_timesheet_model:
                    timesheet_obj = self.env['account.analytic.line'].search([])
                    timesheet_obj.unlink()
                    task_model = self.env['ir.model'].search([('model','=','project.task')])
                    if task_model:
                        task_obj = self.env['project.task'].search([])
                        task_obj.unlink()

            if record.project_task_timesheet:
                project_task_timesheet_model = self.env['ir.model'].search([('model','=','account.analytic.line')])
                if project_task_timesheet_model:
                    timesheet_obj = self.env['account.analytic.line'].search([])
                    timesheet_obj.unlink()
                    task_model = self.env['ir.model'].search([('model','=','project.task')])
                    if task_model:
                        task_obj = self.env['project.task'].search([])
                        task_obj.unlink()
                        project_model = self.env['ir.model'].search([('model','=','project.project')])
                        if project_model:
                            project_obj = self.env['project.project'].search([])
                            project_update_obj = self.env['project.update'].search([])
                            project_update_obj.unlink()
                            project_milestone_obj = self.env['project.milestone'].search([])
                            project_milestone_obj.unlink()
                            project_obj.unlink()

            if record.mrp_order:
                mrp_model = self.env['ir.model'].search([('model','=','mrp.production')])
                if mrp_model:
                    mrp_production_obj = self.env['mrp.production'].search([])
                    mrp_production_obj.action_cancel()
                    workorders_to_delete = mrp_production_obj.workorder_ids.filtered(lambda wo: wo.state != 'done')
                    if workorders_to_delete:
                        workorders_to_delete.unlink()
                    for mrp in mrp_production_obj:
                        mrp.write({'state':'cancel'})
                    mrp_production_obj.unlink()

            if record.bom_mrp_order:
                bom_model = self.env['ir.model'].search([('model','=','mrp.bom')])
                if bom_model:
                    mrp_bom_obj = self.env['mrp.bom'].search([])
                    mrp_bom_obj.unlink()
                    mrp_model = self.env['ir.model'].search([('model','=','mrp.production')])
                    if mrp_model:
                        mrp_production_obj = self.env['mrp.production'].search([])
                        mrp_production_obj.action_cancel()
                        workorders_to_delete = mrp_production_obj.workorder_ids.filtered(lambda wo: wo.state != 'done')
                        if workorders_to_delete:
                            workorders_to_delete.unlink()
                        for mrp in mrp_production_obj:
                            mrp.write({'state':'cancel'})
                        mrp_production_obj.unlink()


            if record.journal_entry:
                move_model = self.env['ir.model'].search([('model','=','account.move')])
                if move_model:
                    journal_entry_obj = self.env['account.move'].search([('move_type','=','entry')])
                    for journal in journal_entry_obj:
                        if journal.state == 'posted':
                            journal.button_draft()
                            journal.line_ids.unlink()
                    journal_entry_obj.unlink()

            if record.invoice_payment_journal:
                move_model = self.env['ir.model'].search([('model','=','account.move')])
                if move_model:
                    journal_entry_obj = self.env['account.move'].search([])
                    journal_entry_obj.line_ids.with_context(dynamic_unlink=True,force_delete=True).unlink()
                    for journal in journal_entry_obj:
                        if journal.state == 'posted':
                            journal.button_draft()
                            journal.line_ids.with_context(dynamic_unlink=True,force_delete=True).unlink()
                    journal_entry_obj.sudo().unlink()

            if record.all_accounting_data:
                move_model = self.env['ir.model'].search([('model','=','account.move')])
                if move_model:
                    property_obj = self.env['ir.property'].search([])
                    for properties in property_obj:
                        properties.unlink()
                        
                    journal_entry_obj = self.env['account.move'].search([])
                    journal_entry_obj.line_ids.with_context(dynamic_unlink=True,force_delete=True).unlink()
                    for journal in journal_entry_obj:
                        if journal.state == 'posted':
                            journal.button_draft()
                            journal.line_ids.with_context(dynamic_unlink=True,force_delete=True).unlink()
                    journal_entry_obj.sudo().unlink()

                    account_line_obj = self.env['account.move.line'].sudo().search([])                 
                    account_line_obj.unlink()

                    account_incoterms_obj = self.env['account.incoterms'].sudo().search([])
                    account_incoterms_obj.unlink()

                    account_reconcile_model_obj = self.env['account.reconcile.model'].sudo().search([])
                    account_reconcile_model_obj.unlink()

                    account_tax_obj = self.env['account.tax'].sudo().search([])
                    account_tax_obj.unlink()

                    account_fiscal_position_obj = self.env['account.fiscal.position'].sudo().search([])
                    account_fiscal_position_obj.unlink()

                    account_journal_group_obj = self.env['account.journal.group'].sudo().search([])
                    account_journal_group_obj.unlink()

                    account_tax_group_obj = self.env['account.tax.group'].sudo().search([])
                    account_tax_group_obj.unlink()

                    payment_acquirer_obj = self.env['payment.provider'].sudo().search([])
                    payment_acquirer_obj.unlink()

                    payment_icon_obj = self.env['payment.icon'].sudo().search([])
                    payment_icon_obj.unlink()

                    payment_token_obj = self.env['payment.token'].sudo().search([])
                    payment_token_obj.unlink()

                    payment_transaction_obj = self.env['payment.transaction'].sudo().search([])
                    payment_transaction_obj.unlink()

                    payment_term_obj = self.env['account.payment.term'].sudo().search([])
                    payment_term_obj.unlink()

                    payment_report_obj = self.env['account.report'].sudo().search([])
                    if not payment_report_obj.variant_report_ids:
                        payment_report_obj.unlink()

                    account_bank_statement_obj = self.env['account.bank.statement'].sudo().search([])
                    account_bank_statement_obj.unlink()

                    account_journal_obj = self.env['account.journal'].search([])
                    account_journal_obj.unlink()

                    account_obj = self.env['account.account'].search([])
                    account_obj.unlink()

            if record.customer_vendor:
                partner_model = self.env['ir.model'].search([('model','=','res.partner')])
                if partner_model:
                    partner_list = []
                    company_obj = self.env['res.company'].search([])
                    for company in company_obj:
                        partner_list.append(company.partner_id.id)
                    partner_obj = self.env['res.partner'].search([('user_ids','=',False),('id','not in',partner_list)])
                   
                    move_model = self.env['ir.model'].search([('model','=','account.move')])
                    if move_model:                   
                        journal_entry_obj = self.env['account.move'].search([])
                        for journal in journal_entry_obj:
                            if journal.state == 'posted':
                                journal.button_draft()
                                journal.line_ids.write({'partner_id':False})
                            journal.write({'partner_id':False})

                        account_payment_register_obj = self.env['account.payment.register'].sudo().search([])
                        for account_payment in account_payment_register_obj:
                            account_payment.write({'partner_id':False})

                        move_line_obj = self.env['account.move.line'].search([])
                        for move_line in move_line_obj:
                            move_line.write({'partner_id':False})

                    purchase_model = self.env['ir.model'].search([('model','=','purchase.order')])
                    if purchase_model:
                        purchase_obj = self.env['purchase.order'].search([])
                        for purchase in purchase_obj:
                            purchase.button_cancel()
                        purchase_obj.unlink()
                        picking_obj = self.env['stock.picking'].search([('picking_type_id.code','=','incoming')])
                        for picking in picking_obj:
                            picking.mapped('move_ids')._action_cancel()
                            picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                        picking_obj.unlink()
                    
                    sale_model = self.env['ir.model'].search([('model','=','sale.order')])
                    if sale_model:
                        sale_obj = self.env['sale.order'].search([])
                        for sale in sale_obj:
                            sale.action_cancel()
                        sale_obj.with_context(force_unlink_saleorder=True).unlink()
                        picking_obj = self.env['stock.picking'].search([('picking_type_id.code','=','outgoing')])
                        for picking in picking_obj:
                            picking.mapped('move_ids')._action_cancel()
                            picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                        picking_obj.unlink()

                    picking_model = self.env['ir.model'].search([('model','=','stock.picking')])
                    if picking_model:
                        picking_obj = self.env['stock.picking'].search([])
                        for picking in picking_obj:
                            picking.mapped('move_ids')._action_cancel()
                            picking.with_context(prefetch_fields=False).mapped('move_ids').unlink()  # Checks if moves are not done
                        picking_obj.unlink()
                        
                    partner_obj.unlink()
            


