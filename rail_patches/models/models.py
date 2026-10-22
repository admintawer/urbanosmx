# -*- coding: utf-8 -*-
from odoo import  models, _

class AccountMove(models.Model):
    _inherit = 'account.move'


    def _l10n_mx_edi_cfdi_invoice_try_send(self):
        """ Try to generate and send the CFDI for the current invoice. """
        self.ensure_one()
        if self.state != 'posted' or self.l10n_mx_edi_cfdi_state not in (False, 'cancel', 'global_cancel'):
            return

        # == Check the config ==
        errors = self._l10n_mx_edi_cfdi_check_invoice_config()
        if errors:
            self._l10n_mx_edi_cfdi_invoice_document_sent_failed("\n".join(errors))
            return

        # == Set the post time and commit ==
        if not self.l10n_mx_edi_post_time:
            self.l10n_mx_edi_post_time = self.env['l10n_mx_edi.document']._get_min_of_now_and_document_date(
                self.invoice_date,
                self.company_id.partner_id.commercial_partner_id,
                self.journal_id,
            )

            if self.env['l10n_mx_edi.document']._can_commit():
                self._cr.commit()

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # == Send ==
        def on_populate(cfdi_values):
            self._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            if error == 'empty_cfdi':
                self._l10n_mx_edi_cfdi_invoice_document_empty()
            else:
                self._l10n_mx_edi_cfdi_invoice_document_sent_failed(error, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)

        def on_success(_cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            if addendas_post_send := self.l10n_mx_edi_addenda_ids._filter_addenda_by_xml_node('addenda'):
                append_values = self._l10n_mx_edi_cfdi_invoice_append_addendas(
                    cfdi_str=cfdi_str,
                    addendas=addendas_post_send,
                )
                if append_values.get('errors'):
                    self.message_post(body=_("Error when decoding the addenda to append after signing:\n%s",
                                             '\n'.join(append_values['errors'])))
                cfdi_str = append_values['cfdi']

            document = self._l10n_mx_edi_cfdi_invoice_document_sent(cfdi_filename, cfdi_str)
            self.message_post(
                    body=_("The CFDI document was successfully created and signed by the government."),
                    attachment_ids=document.attachment_id.ids,
                )

        qweb_template = self.env['l10n_mx_edi.document']._get_invoice_cfdi_template()
        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            qweb_template,
            self._l10n_mx_edi_get_invoice_cfdi_filename(),
            on_populate,
            on_failure,
            on_success,
        )
        if (
            (doc := self.l10n_mx_edi_invoice_document_ids.sorted()[0])
            and doc.state == 'invoice_sent'
            and (original_doc := doc._get_original_document())
            and original_doc.state == 'invoice_sent'
            and self.move_type == 'out_invoice'
        ):
            original_doc.move_id._l10n_mx_edi_cfdi_invoice_try_cancel(original_doc, '01')
