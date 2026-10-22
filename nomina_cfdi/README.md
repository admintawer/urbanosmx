# nomina_cfdi (puente de migración)

Este módulo conserva el nombre técnico instalado en la base v16, pero no
reactiva el motor CFDI antiguo. Al actualizarlo en Odoo 19:

1. archiva las filas legacy completas en `rail.payroll.migration.archive`;
2. copia campos con equivalencia inequívoca a `hr.version`, modelos nativos MX
   y modelos `rail_l10n_mx_payroll_*`;
3. deja las columnas y tablas sin equivalencia dentro del archivo auditable;
4. delega la operación futura en la localización mexicana nativa de Odoo 19.

No debe desinstalarse antes de validar conteos, importes, XML timbrados,
préstamos, vacaciones e incidencias contra la base v16.
