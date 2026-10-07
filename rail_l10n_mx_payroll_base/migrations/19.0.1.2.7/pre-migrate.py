# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Convert the 1.2.6 integer payroll number column to the selection storage type."""
    cr.execute("""
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'hr_payslip_run'
           AND column_name = 'rail_payroll_number'
    """)
    row = cr.fetchone()
    if not row:
        return

    data_type = row[0]
    if data_type in ('integer', 'bigint', 'smallint'):
        cr.execute("""
            ALTER TABLE hr_payslip_run
            ALTER COLUMN rail_payroll_number TYPE varchar
            USING CASE
                WHEN rail_payroll_number BETWEEN 1 AND 8 THEN rail_payroll_number::varchar
                ELSE NULL
            END
        """)
    else:
        cr.execute("""
            UPDATE hr_payslip_run
               SET rail_payroll_number = NULL
             WHERE rail_payroll_number IS NOT NULL
               AND rail_payroll_number NOT IN ('1','2','3','4','5','6','7','8')
        """)
