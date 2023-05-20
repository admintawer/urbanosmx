# -*- coding: utf-8 -*-
from odoo import api, models, fields, tools, _
import logging
_logger = logging.getLogger(__name__)

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        # OVERRIDE
        vals = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        def filter_void_tax_line(inv_line):
            return inv_line.discount != 100.0
        
        def filter_tax_withholding(base_line, tax_values):
            tax = tax_values['tax_repartition_line'].tax_id
            return tax.amount < 0.0 and not tax.local_tax
        
        def filter_tax_local_withholding(base_line, tax_values):
            tax = tax_values['tax_repartition_line'].tax_id
            return tax.amount < 0.0 and tax.local_tax

        vals['tax_details_withholding'] = invoice._prepare_edi_tax_details(filter_to_apply=filter_tax_withholding, filter_invl_to_apply=filter_void_tax_line)
        vals['tax_details_local_withholding'] = invoice._prepare_edi_tax_details(filter_to_apply=filter_tax_local_withholding, filter_invl_to_apply=filter_void_tax_line)

        _logger.critical('IMPUESTOS LOCALES')
        _logger.critical(vals['tax_details_local_withholding']['tax_details'])
        _logger.critical('RETENCIONES')
        _logger.critical(vals['tax_details_withholding']['tax_details_per_record']['line'])

        return vals