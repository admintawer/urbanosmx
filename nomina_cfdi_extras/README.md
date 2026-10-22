# nomina_cfdi_extras (puente de migración)

Mantiene el nombre técnico del módulo v16 durante la actualización. Los
modelos cuyos nombres y tablas se conservaron (`employee.loan`,
`installment.line` y `viaticos.nomina`) son tomados directamente por
`rail_l10n_mx_payroll_extras`.

Las tablas antiguas de faltas, retardos, incapacidades, incidencias, vacaciones
y feriados se archivan completas antes de cualquier transformación funcional.
No se generan ausencias automáticamente durante la actualización porque hacerlo
podría recalcular work entries o recibos históricos; esa conversión debe
ejecutarse y conciliarse como una segunda fase controlada.
