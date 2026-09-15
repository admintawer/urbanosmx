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


## Semántica salarial México v19

Para salario fijo MX, `hr.version.wage` se conserva como sueldo contractual mensual, igual que en la localización v18 compartida. El sueldo diario se obtiene de `l10n_mx_days_per_month`; `schedule_pay` define únicamente la periodicidad de pago y los días del periodo mediante `l10n_mx_schedule_table`.


## Wage type y periodicidad nativa en Odoo 19

En `hr.version`, `wage_type` **no** representa semanal/quincenal/mensual. Sus valores
son `monthly` (salario fijo) y `hourly` (salario por hora). La periodicidad real de
pago se almacena en el campo nativo `schedule_pay`, cuyo valor se deriva normalmente
de `hr.payroll.structure.type.default_schedule_pay`.

Para salario fijo MX en esta migración, `wage` se interpreta como sueldo contractual
mensual. El sueldo diario se calcula con `l10n_mx_days_per_month`, y `schedule_pay`
solo define la frecuencia/días del periodo mediante `l10n_mx_schedule_table`. Para
`wage_type = hourly`, se conserva el flujo nativo basado en `hourly_wage`.

Los campos custom legacy de percepciones/deducciones permanecen en el modelo para
migración, pero se retiraron de la interfaz. La captura operativa se centraliza en
`rail_other_entry_ids`.

## Periodicidad y SBC en Odoo 19

- `wage_type` distingue salario fijo (`monthly`) de salario por hora (`hourly`).
- `schedule_pay` es la periodicidad nativa de pago (semanal, quincenal, mensual, etc.).
- Para salario fijo MX, `wage` se interpreta como salario contractual mensual.
- El salario diario para SBC se obtiene con `wage / l10n_mx_days_per_month`; cambiar `schedule_pay` no recalcula el SBC.
- `rail_payment_type` se conserva solo como campo legacy y ya no se propaga a nuevas `hr.version`.
