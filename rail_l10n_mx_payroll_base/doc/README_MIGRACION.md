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

## Periodos de nómina MX

Desde 19.0.1.2.6 se extiende `hr.payslip.run` sin reemplazar el comportamiento nativo de Odoo 19:

- `schedule_pay` continúa siendo el calendario/frecuencia de pago nativo.
- Odoo 19 completa `date_end` automáticamente a partir de `schedule_pay` y `date_start`; el módulo no duplica esa lógica.
- `rail_l10n_mx_payroll_type` muestra el tipo CFDI de la estructura salarial (`O` ordinaria / `E` extraordinaria).
- `rail_payroll_number` permite capturar el consecutivo operativo de nómina.
- `rail_period_days` calcula los días calendario inclusivos entre `date_start` y `date_end`.


## 19.0.1.2.7 - Lotes de nómina

- `schedule_pay` (Calendario de pago) conserva exclusivamente la frecuencia de pago y el cálculo nativo del periodo.
- `rail_l10n_mx_payroll_type` vuelve a ser una selección funcional (Ordinaria/Extraordinaria) y filtra `structure_id` por `l10n_mx_payroll_type`.
- `rail_payroll_number` es selección de 1 a 8, como en el flujo funcional legado.
- El antiguo concepto de "Configuración" no se duplica: en Odoo 19 la estructura efectiva es `structure_id`; la frecuencia queda en `schedule_pay`.

## 19.0.1.2.8 - Alias operativo del lote de nómina

- Se agrega `hr.payslip.run.rail_payroll_alias` como nombre manual/operativo del lote.
- El campo `name` nativo permanece intacto y continúa siendo generado por Odoo.
- El alias se captura desde el formulario/wizard de creación del lote y se muestra en formulario, lista y kanban.
- El alias también está disponible como criterio de búsqueda en la vista search de lotes.

