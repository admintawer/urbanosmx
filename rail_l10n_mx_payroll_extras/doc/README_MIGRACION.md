# rail_l10n_mx_payroll_extras — Odoo 19

Módulo de préstamos, descuentos periódicos y viáticos sobre `hr_payroll` nativo de Odoo 19.
No depende de `om_hr_payroll`, `nomina_cfdi_ee` ni `tablas.cfdi`.

## Préstamos y cuotas

- Las cuotas se reservan desde que un recibo está en borrador para impedir que dos recibos tomen la misma parcialidad.
- Al validar el recibo, la cuota reservada queda pagada.
- Al cancelar o eliminar el recibo, la reserva/pago se revierte sin cancelar el préstamo.
- Si el préstamo estaba cerrado y se revierte una cuota, vuelve a estado activo en nómina.
- La lista de cuotas muestra explícitamente `display_name` como columna **Cuota**.
- Omitir una cuota crea una cuota reprogramada al final del calendario y publica trazabilidad en el chatter de la cuota y del préstamo.
- Reactivar una cuota elimina la reprogramación si todavía no fue reservada ni pagada y publica trazabilidad.

## Viáticos

Se incluyen dos estructuras extraordinarias mexicanas:

- `RAIL_MX_VIAT_DELIVERY`: entrega de viáticos, percepción `VIAT`.
- `RAIL_MX_VIAT_CHECK`: comprobación con percepción `PVIAT` y deducción compensatoria `DVIAT`.

Características:

- La entrega y la comprobación generan recibos extraordinarios separados.
- Los recibos quedan en borrador pero calculados, listos para revisión, validación y timbrado.
- No incluyen préstamos/descuentos ordinarios.
- Se pueden seleccionar varios viáticos desde la lista y generar recibos por lote.
- Se crea un `hr.payslip.run` por compañía, fecha y tipo de operación.
- Cada línea de entrega/comprobación conserva el recibo que la procesó.
- Cancelar/eliminar el recibo libera las líneas para poder regenerarlas.

### Configuración requerida

Antes de validar/timbrar, configurar diario y cuentas contables en las estructuras/reglas de viáticos según la contabilidad del cliente:

- México: Entrega de viáticos.
- México: Comprobación de viáticos.

## Pruebas funcionales mínimas

1. Crear dos recibos borrador del mismo empleado y comprobar que una cuota no pueda reservarse en ambos.
2. Validar un recibo y confirmar que la cuota quede pagada.
3. Cancelar ese recibo y confirmar que la cuota se libere y el préstamo permanezca activo.
4. Omitir una cuota y revisar chatter del préstamo y de la cuota.
5. Reactivar una cuota y comprobar que se elimine la cuota reprogramada.
6. Crear una entrega de viáticos y generar recibo extraordinario calculado.
7. Crear comprobación y generar un segundo recibo extraordinario independiente.
8. Seleccionar viáticos de varios empleados y generar los recibos en lote.
9. Cancelar un recibo de viáticos y comprobar que las líneas vuelvan a pendientes.
10. Validar y timbrar ambos tipos de recibo después de configurar diario/cuentas.
