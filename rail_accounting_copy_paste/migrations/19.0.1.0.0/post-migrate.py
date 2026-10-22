def migrate(cr, version):
    cr.execute("""
        UPDATE account_tax
           SET l10n_mx_tax_type = 'local'
         WHERE local_tax IS TRUE
           AND COALESCE(l10n_mx_tax_type, '') != 'local'
    """)
