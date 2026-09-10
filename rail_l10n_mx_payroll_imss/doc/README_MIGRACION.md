# rail_l10n_mx_payroll_imss

Migración funcional de `nomina_cfdi_sua` y `nomina_cfdi_sbc` hacia Odoo 19.

## Criterios confirmados

- No se migra `tablas.cfdi` como modelo principal.
- Registro patronal: se usa `res.company.l10n_mx_imss_id` nativo.
- Código postal: se usa `hr.version.private_zip` / `hr.employee.private_zip` nativo.
- Nombre separado: se conserva desde `rail_l10n_mx_payroll_base`.
- Cambio SBC: crea una nueva `hr.version`, equivalente al nuevo `hr.contract` que se creaba en v18.
- Reglas variables IMSS/SBC: se toman de `hr.salary.rule.rail_sbc_variable*` del módulo base.

## Alcance

- Incidencias IMSS/SUA/IDSE.
- Campos SUA/IDSE versionables en `hr.version`.
- Campos de incapacidad IMSS en `hr.leave`.
- Exportador SUA/IDSE.
- Cálculo SBC bimestral y creación de nueva `hr.version`.

## Pendiente de validación funcional

Los layouts se generan con estructura migrada y helpers separados. Deben validarse contra los archivos aceptados por SUA/IDSE del cliente antes de producción.

## Versión 19.0.1.0.3 - catálogo legacy

Al instalar o actualizar el módulo se configura de forma idempotente el catálogo técnico:

- DFES: Día festivo
- FI: Falta injustificada
- FJC: Falta con goce de sueldo
- FJS: Falta sin goce de sueldo
- FR: Falta por retardo
- INC_EG: Incapacidad por enfermedad general
- INC_MAT: Incapacidad por maternidad
- INC_RT: Incapacidad por riesgo de trabajo
- SEPT: Séptimo día
- VAC: Vacaciones
- WORK100: Asistencia (registro nativo de Odoo, no se duplica)

También se crean o actualizan los tipos de ausencia aplicables y se enlazan
con su tipo de entrada de trabajo. Las incapacidades conservan el código SAT
nativo correspondiente para CFDI de nómina.

## 19.0.1.0.4 - Eventos automáticos IMSS

- Primera versión con inicio de contrato: crea evento `hire`.
- Primer registro de un contrato posterior: crea `reentry`.
- Cambio efectivo de `wage`, `hourly_wage` o SBC: crea/consolida `salary_change`.
- Cálculo SBC bimestral: crea nueva `hr.version` y evento `salary_change` con origen `sbc_bimonthly`.
- Asistente nativo de salida: crea evento `leave`.
- Los eventos incompletos quedan en borrador y se confirman automáticamente al tener NSS, registro patronal, datos SUA y SBC.
- Acción de empleado **Sincronizar incidencias IMSS** para reconstruir eventos faltantes en datos ya migrados.
- Contexto para migraciones masivas: `rail_skip_imss_auto_incidence=True`.

## Altas IMSS retroactivas (19.0.1.0.6)

- En la primera actualización a esta versión se ejecuta un backfill idempotente.
- Se toma la primera `hr.version` histórica de cada empleado, incluyendo archivados.
- La fecha del Alta se obtiene de `contract_date_start` y, si falta, de `date_version`.
- Si ya existe un Alta activa para el empleado, no se duplica.
- Los eventos con datos completos quedan Confirmados; los incompletos quedan en Borrador.
- El proceso puede repetirse manualmente desde Nómina > Reportes > IMSS / SUA / IDSE > Reconstruir altas retroactivas.


## Cambios 19.0.1.0.7

- Los campos `rail_imss_clinic`, `rail_imss_subdelegation_code`,
  `rail_imss_worker_type`, `rail_imss_salary_type` y
  `rail_imss_workday_type` se almacenan en `hr.employee`.
- `hr.version` conserva proxies related con los mismos nombres técnicos para
  compatibilidad.
- La actualización migra valores legacy desde las columnas históricas de
  `hr.version` sin sobrescribir datos ya capturados en el empleado.
- Las validaciones y exportaciones SUA/IDSE leen la información del empleado.
- Los menús se ubican en Empleados > Reportes > SUA / IDSE.


## SBC único

El cálculo bimestral siempre parte del SBC base recalculado desde `wage` y el factor de integración; no suma la nueva variable sobre el SBC vigente anterior. El resultado total se guarda en `hr.version.rail_fixed_sbc`.
