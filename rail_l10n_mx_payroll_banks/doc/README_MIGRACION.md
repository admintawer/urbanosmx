# rail_l10n_mx_payroll_banks

Migración funcional de `nomina_cfdi_bancos` a Odoo 19.

## Criterios

- No depende de `om_hr_payroll` ni `nomina_cfdi_ee`.
- Extiende el wizard nativo `hr.payroll.payment.report.wizard`.
- Usa `compute_salary_allocations()` de Odoo 19 para respetar cuentas bancarias y distribución salarial.
- Usa `res.partner.bank` para datos específicos de cuenta/banco.
- El campo legacy `employee.diario_pago` se reemplaza por `payment_journal_id` del wizard.
- Los nombres separados vienen de `rail_l10n_mx_payroll_base`.

## Validaciones funcionales obligatorias

1. Generar layout BBVA mixto con cuenta cheques y CLABE.
2. Generar layout BBVA solo BBVA.
3. Generar layout Santander solo Santander con nombre separado.
4. Generar layout Santander mixto con clave banco y plaza en `res.partner.bank`.
5. Generar layout Banamex C y D.
6. Generar layout Banorte `.pag`.
7. Generar layout Banregio `.csv`.
8. Generar layout HSBC `.csv`.
9. Generar layout Scotiabank.
10. Generar layout Inbursa `.csv`.
11. Generar layout Banbajío.
12. Validar empleado sin cuenta bancaria: debe mostrar error claro.
13. Validar recibos cancelados/no validados: no deben incluirse.
14. Validar distribución salarial con múltiples cuentas bancarias.
15. Comparar layouts contra archivos reales aceptados por bancos antes de producción.

## Notas

Los layouts fueron adaptados desde `nomina_cfdi_bancos` v18, pero deben validarse con archivos reales aceptados por cada banco porque los bancos pueden cambiar especificaciones.


## Inbursa (19.0.1.0.3)

El layout Inbursa se genera como TXT sin encabezado ni totales, con cinco columnas separadas por coma:

1. Consecutivo (máximo 5 dígitos).
2. Número de empleado (numérico, máximo 10 dígitos).
3. Nombre del empleado (máximo 50 caracteres).
4. Cuenta de abono (exactamente 11 dígitos).
5. Monto (dos decimales, máximo 15 dígitos).

El campo anterior `inbursa_cuenta` se conserva técnicamente por compatibilidad, pero ya no forma parte del archivo.
