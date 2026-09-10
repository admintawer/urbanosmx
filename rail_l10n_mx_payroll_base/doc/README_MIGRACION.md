# rail_l10n_mx_payroll_base

Módulo base para la migración de nómina mexicana hacia Odoo 19.

## Criterios aplicados

- No depende de `om_hr_payroll`.
- No migra `tablas.cfdi` como modelo principal.
- Usa `hr.version` como destino de datos laborales que antes vivían en `hr.contract`.
- Usa campos nativos v19 para RFC, CURP, NSS, periodicidad, régimen, jornada, INFONAVIT, FONACOT y timbrado CFDI.
- Conserva nombre separado porque los layouts v18 lo usaban explícitamente.

## Contenido

- Campos de nombre separado en `hr.employee`.
- Campos custom versionables en `hr.version`.
- Campos de integración variable IMSS/SBC en `hr.salary.rule`.
- Helper `rail_create_new_version()` para flujos que en v18 creaban un nuevo `hr.contract`.

## Pendiente para módulos siguientes

- Reglas salariales custom que consuman los campos de bonos/deducciones.
- Migración de vacaciones.
- Migración de préstamos/viáticos.
- Migración SUA/IDSE/SBC.
- Layouts bancarios.
- Cálculo inverso.


## Consolidación SBC

`rail_fixed_sbc` es el único campo destino para `sueldo_base_cotizacion` y `sbc_fijo` de v18. Se prioriza `sueldo_base_cotizacion` y se usa `sbc_fijo` solo como respaldo durante la migración.
