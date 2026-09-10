# rail_l10n_mx_payroll_accounting

Extensiones contables de nómina mexicana para Odoo 19.

## Criterio de migración

Este módulo no reemplaza `hr_payroll_account`. La generación contable base de recibos, cancelación y asientos sigue siendo la nativa de Odoo 19.

Se migran únicamente las personalizaciones legacy que no quedan cubiertas por Odoo 19:

- Cuentas contables especiales por empleado o departamento en reglas salariales.
- Configuración contable para póliza IMSS patronal.
- Wizard de póliza IMSS patronal con importes editables y carga opcional desde líneas de recibo.

## No migrado desde v18

- Overrides completos de `action_payslip_done` y `action_payslip_cancel`.
- `move_id`, `journal_id` o `date` custom de recibos.
- `tablas.cfdi` como fuente de cuentas o parámetros.
- Generación contable completa basada en `om_hr_payroll_account_ee`.

## Pruebas funcionales mínimas

1. Validar un recibo estándar y confirmar que genera asiento nativo.
2. Configurar una cuenta especial por empleado en una regla salarial y validar que sustituye la cuenta estándar.
3. Configurar una cuenta especial por departamento y validar que aplica a empleados del departamento.
4. Validar que si no hay cuenta especial se usa la cuenta estándar de la regla.
5. Cancelar un recibo con asiento y confirmar que usa el flujo nativo de Odoo.
6. Configurar cuentas de póliza IMSS en Ajustes de Nómina.
7. Generar póliza IMSS patronal con importes manuales.
8. Generar póliza IMSS patronal cargando importes desde códigos de reglas en recibos.
9. Confirmar que el asiento IMSS queda balanceado.
10. Comparar una póliza IMSS contra v18 usando un caso real.

## Ajuste 19.0.1.0.1 — compañía de mapeos contables

En Odoo 19 `hr.salary.rule` no contiene `company_id`. El mapeo contable ahora define su compañía explícitamente y filtra los mapeos durante la contabilización por `payslip.company_id`.

### Prueba de regresión obligatoria

1. Instalar/actualizar el módulo sin errores de registro.
2. Crear un mapeo para una regla salarial y una compañía.
3. Confirmar que solo permita empleados, departamentos y cuentas compatibles con dicha compañía.
4. En entorno multiempresa, validar que una nómina no tome mapeos de otra compañía.
