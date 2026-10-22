# rail_l10n_mx_payroll_reports

Reportes operativos de nómina mexicana para Odoo 19.

## Origen funcional

Migra el bloque de reportes de `nomina_cfdi_extras_ee` hacia la nómina nativa v19. No depende de `om_hr_payroll`, `report_xlsx` ni `tablas.cfdi`.

## Reportes incluidos

- Total por empleado.
- Total por departamento.
- Detalle por reglas salariales.
- Cálculo ISR anual con acumulados por recibo.
- ISN con base configurable por códigos de reglas.
- IMSS con códigos configurables o detección por tokens.
- Caja / fondo de ahorro.
- Altas y bajas IMSS desde `rail.imss.incidence`.
- Liquidaciones.
- PTU / reparto de utilidades.

## Criterio técnico

Los reportes leen `hr.payslip`, `hr.payslip.line`, `hr.version`, `hr.employee` y `rail.imss.incidence`.
El cálculo final depende de los recibos ya calculados/validados por el motor de nómina v19.

## Validación funcional

Los códigos de reglas deben configurarse por el funcional cuando el reporte requiera una base específica. Si se dejan vacíos, se usan códigos estándar o detección por tokens, por lo que los resultados deben compararse contra v18 antes de producción.


## Reporte IMSS

Incluye el campo único `hr.version.rail_fixed_sbc` con la etiqueta Sueldo base de cotización (IMSS).
