# Argentina - ARCA WSCT Factura T para Odoo 17 CE

Módulo para Odoo 17 Community Edition que incorpora la emisión de Factura T,
Nota de Débito T y Nota de Crédito T mediante el Web Service de Comprobantes
de Turismo (WSCT) de ARCA.

## Contenido

* `l10n_ar_afipws_wsct/`: código fuente instalable del módulo.
* `docs/Instructivo_instalacion_Factura_T_WSCT.docx`: instalación y
  configuración técnica.

## Requisitos

* Odoo 17 Community Edition.
* Módulo `l10n_ar_afipws_fe` instalado.
* Biblioteca Python `pyafipws`.
* Certificado ARCA con el servicio `wsct` autorizado.
* Punto de venta habilitado para WSCT.

## Instalación rápida

Copiar la carpeta `l10n_ar_afipws_wsct` dentro de una ruta de addons,
actualizar la lista de Aplicaciones e instalar o actualizar el módulo.

Para un despliegue con Docker:

```bash
cd /app/extra-addons
unzip -o l10n_ar_afipws_wsct.zip
docker restart odoo_app
```

Luego se debe seguir el instructivo en `docs/` y realizar pruebas en
homologación antes de emitir en producción.

## Configuración fiscal de Factura T

La factura usa dos impuestos nativos de Odoo sobre la línea:

* IVA ventas 21 %.
* Reintegro IVA -21 %.

Además de crear ambos impuestos, se debe crear un grupo de impuestos exclusivo
para el reintegro, llamado **Reintegro de IVA 21 %**, y asignarlo al impuesto
**Reintegro IVA -21 %**. El impuesto positivo debe permanecer en el grupo
**IVA 21 %**. No deben compartir el mismo grupo: Odoo agrupa sus importes en el
resumen de la factura y, si ambos están en el grupo de IVA, el resultado puede
mostrarse como $ 0,00 en lugar de exhibir el IVA y su reintegro por separado.

El IVA se informa y se visualiza en el comprobante, mientras que el reintegro
lo compensa para que el importe total sea el neto cobrado al turista.

## Seguridad

No incluir en este repositorio certificados, claves privadas, tokens, bases de
datos, copias de seguridad, archivos `.env`, logs ni datos reales de pasajeros.

## Autoría y licencias

Copyright (C) 2026 Alfredo Sanz. Consulte también el archivo `NOTICE`.

El código se distribuye bajo la licencia GNU Affero General Public License
v3.0 o posterior (AGPL-3.0-or-later). Consulte el archivo `LICENSE`.

La documentación dentro de `docs/` se distribuye bajo la licencia
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.es).
