# Rail Mexican Payroll Inverse Calculation

Migración funcional de `nomina_inverso` v18 hacia Odoo 19 nativo.

## Criterio de migración

- No depende de `om_hr_payroll`.
- No depende de `tablas.cfdi`.
- No migra fórmulas manuales de ISR, subsidio e IMSS.
- Usa el motor real de `hr_payroll` / `l10n_mx_hr_payroll`.
- El usuario selecciona la estructura salarial real que desea simular.
- El cálculo inverso converge contra la regla `NET` calculada por esa estructura.
- Al confirmar crea una nueva `hr.version`.

## Técnica de simulación

Durante cada iteración se crea un recibo temporal en borrador con contexto:

- `salary_simulation=True`
- `rail_inverse_candidate_wage=<salario candidato>`
- `rail_inverse_version_id=<hr.version>`

El módulo sobreescribe `hr.version._get_contract_wage()` únicamente cuando ese contexto está activo.
La localización mexicana también toma el salario candidato para el salario diario usado por las reglas IMSS.

Cada recibo temporal se elimina al finalizar su iteración.

En la iteración final, antes de eliminar el recibo, todas sus líneas calculadas se copian a
`rail.payroll.inverse.simulation.line`. De esta manera el wizard puede mostrar la misma información
funcional del cálculo de reglas de un recibo: nombre, código, categoría, cantidad, tasa, importe,
total y acumulado.

## Estructura salarial

El wizard precarga la estructura predeterminada de la versión laboral, pero permite seleccionar otra
estructura del mismo país. La estructura debe tener reglas configuradas y una regla con código `NET`.

No se duplica automáticamente la estructura `MX_REGULAR`; la simulación usa la estructura real elegida
para evitar divergencias entre reglas productivas y reglas de simulación.

## Archivo de importación masiva

Columnas de identificación:

- `No. empleado`, para empleados existentes; o
- `Nombre candidato`, cuando todavía no existe número de empleado.

Columnas de cálculo:

- `Neto deseado` (obligatoria).
- `Periodicidad neto`.
- `Estructura salarial` (preferentemente código, por ejemplo `MX_REGULAR`; también acepta nombre exacto).
- `Periodicidad nómina`, obligatoria para candidatos sin versión laboral utilizable.
- `Fecha estimada ingreso`, obligatoria para simulación prospectiva.
- `Prima vacacional (%)`, obligatoria para simulación prospectiva.
- `Última nómina del mes` y `Mes`, únicamente para empleados con historial real.
- `Fecha efectiva`.
- `SBC`.

Si existe `No. empleado`, se busca por `hr.employee.registration_number`. Si solo existe nombre, se intenta
resolver un empleado por nombre exacto; si no existe se simula como candidato sin crear una ficha permanente.

## Pruebas funcionales mínimas

1. Abrir el wizard desde la ficha del empleado y validar la estructura precargada.
2. Seleccionar una estructura salarial distinta y confirmar que sus reglas aparezcan en el detalle.
3. Calcular un neto objetivo individual y verificar que la línea `NET` coincida con el resultado mostrado.
4. Comparar ISR, IMSS, INFONAVIT/FONACOT u otras deducciones contra un recibo real calculado con la misma estructura.
5. Confirmar el cálculo y crear una nueva `hr.version`.
6. Calcular nómina real con la nueva versión y comparar el NET contra el objetivo.
7. Probar última nómina del mes contra reglas de ajuste de subsidio/ISR.
8. Importar Excel masivo con estructura por código y sin estructura (default).
9. Importar Excel con empleado o estructura inexistente y validar el error por línea.
10. Validar que los recibos temporales no queden en nómina.

## SBC

El wizard no crea un campo SBC alterno. Si no se captura un SBC temporal, la nueva versión calcula
`rail_fixed_sbc` desde el salario resultante; si se captura, ese valor se guarda en el mismo campo
autoritativo.

## Ajuste 19.0.1.1.7

- Estructura salarial visible y obligatoria en el wizard individual.
- El objetivo del algoritmo es el `NET` nativo de la estructura seleccionada.
- Nuevo `One2many` de reglas calculadas, con formato equivalente al tab de cálculo salarial del recibo.
- Se conserva el salario candidato sin escribir en `hr.version` durante las iteraciones.
- Importación masiva acepta `Estructura salarial` por código o nombre exacto.
- Plantilla XLSX actualizada e incluida en `doc/Plantilla_importacion_nomina_inversa_Odoo19.xlsx`.


## 19.0.1.1.8 - simulación de candidatos sin hr.version

- El cálculo inverso ya no requiere una `hr.version` persistente.
- Desde la ficha de un empleado cuya contratación todavía no tiene fecha de inicio válida, la simulación usa un empleado/perfil técnico temporal separado; no se altera el historial real de `hr.version`.
- Se agregó `Cálculo inverso > Simulación candidato` para escenarios donde todavía no existe ni siquiera una ficha de empleado persistente; se crea un perfil técnico temporal y se elimina después de copiar las reglas calculadas al wizard.
- Para candidatos sin versión se solicita periodicidad de nómina, fecha estimada de ingreso y prima vacacional aplicable, porque las reglas nativas mexicanas usan esos datos para salario diario e integración IMSS.
- La importación masiva acepta `Nombre candidato` cuando no existe `No. empleado`.
- Si el nombre no corresponde a un empleado existente, la línea puede calcularse como simulación prospectiva sin crear empleado ni versión permanentes.
- `Crear versión laboral` solo está disponible cuando existe una ficha `hr.employee` real.


## 19.0.1.1.9
- Corrige simulaciones prospectivas (empleado sin versión utilizable y candidato sin empleado).
- Durante `salary_simulation`, el factor de integración MX usa la fecha estimada de ingreso capturada en el wizard en lugar del historial técnico temporal.
- Evita `KeyError(0)` al consultar `l10n_mx_holiday_tables`: una simulación prospectiva se considera desde el primer año de antigüedad.
- La nómina normal fuera del cálculo inverso conserva el cálculo nativo de Odoo.
