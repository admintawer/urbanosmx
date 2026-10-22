# rail_l10n_mx_payroll_vacations

Módulo de migración del control de vacaciones v18 hacia Odoo 19.

## Criterios aplicados

- No depende de `om_hr_payroll`.
- No usa `hr.contract`.
- No migra `tablas.cfdi`.
- Usa `hr.version` para los saldos vacacionales versionables.
- Usa el parámetro nativo `l10n_mx_holiday_tables` de Odoo 19 para generar días por aniversario.
- Respeta la lógica nativa de `hr_holidays` y `hr_work_entry_holidays`; no fuerza estados manualmente.

## Flujo

1. Marcar el tipo de ausencia de vacaciones con código `VAC` o con el check `Controlar saldo vacacional MX`.
2. Generar saldos vacacionales por empleado/version manualmente o con el cron anual.
3. Al validar vacaciones, se consumen los saldos activos más antiguos o la línea seleccionada.
4. Al rechazar/cancelar, se devuelven exactamente los días consumidos.
5. Al crear una nueva `hr.version`, se copian los saldos vigentes desde la versión anterior.

## Pruebas funcionales del módulo

- Crear tabla/saldo de vacaciones en una versión laboral.
- Aprobar vacaciones y validar descuento de días.
- Cancelar vacaciones aprobadas y validar devolución.
- Rechazar vacaciones y validar devolución.
- Aprobar vacaciones cruzando cambio de versión laboral.
- Ejecutar cron anual de vacaciones.
- Generar nómina con vacaciones y validar work entries nativas.
- Probar empleado sin saldo suficiente y validar error funcional.

## Ajuste 19.0.1.0.1 — antigüedad entre versiones

- La antigüedad ya no se calcula desde `hr.version.contract_date_start` de la versión vigente.
- Se usa `hr.employee._get_first_contract_date(no_gap=False)` para considerar el primer contrato histórico.
- Se muestran la fecha inicial y los años completos de antigüedad.
- Cada saldo guarda fecha inicial, años de antigüedad y aniversario aplicado.
- El botón **Generar / recalcular saldo anual** corrige saldos automáticos creados con la lógica anterior.
- El cron anual utiliza el aniversario del primer contrato, no el inicio de la versión actual.

### Prueba de regresión obligatoria

1. Crear un empleado con contrato 1 desde 2020 hasta 12/07/2025.
2. Crear contrato/versión 2 desde 13/07/2025.
3. Ejecutar la generación de saldo en la versión vigente.
4. Verificar que la fecha inicial de antigüedad sea la del contrato de 2020.
5. Verificar que los años y días otorgados correspondan a la tabla nativa mexicana para la antigüedad acumulada.
