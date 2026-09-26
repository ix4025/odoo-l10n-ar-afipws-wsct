# l10n_ar_afipws_wsct

Odoo 17 CE extension for ARCA WSCT (Factura T). It inherits `l10n_ar_afipws`
and `l10n_ar_afipws_fe`; it never edits either module.

## Install in homologation

1. Unzip this module inside an addons path and update the Apps list.
2. Install **Argentina - AFIP WSCT Factura T**.
3. In the company AFIP certificate alias, authorize the WSCT service in ARCA and
   set the Odoo environment to **Homologation**.
4. Create a dedicated sales journal. Select AFIP POS system **Tourism vouchers
   - Factura T (WSCT)** and the ARCA point-of-sale number enabled for WSCT.
   Do not reuse an A/B journal or point of sale.
5. The module creates the ARCA WSCT document types: 195 Factura T, 196 Nota
   de Débito T and 197 Nota de Crédito T. Confirm that they remain enabled
   for your point of sale with `WSCT document types`. The dedicated WSCT
   journal filters its document selector to those three types.
6. Complete the WSCT tourism code on every product, and enter the payment method
   code on every WSCT invoice. Use **Update WSCT catalogs** in the journal to
   obtain both lists from WSCT, then select them from the product and invoice.
   Configure the journal with a 21% sales VAT tax and a matching -21% VAT
   reimbursement tax. The invoice must show both taxes so that ARCA receives
   the VAT detail while the final amount remains the net amount charged to the
   tourist.
   For a card payment, refresh the card types from the invoice and store only
   the first six digits of the card; never enter its complete number.
7. Use **Get Connection**, **Dummy Test**, then issue a homologation voucher.

## Safety and scope

* Production is available only when the company environment is changed to
  production; this module defaults nothing to production.
* The module does not alter A/B documents, certificates, sequences or existing
  invoices. The dedicated WSCT journal must be configured by the operator with
  its own taxes and point of sale.
* WSCT response expiry dates are normalized for the Odoo 17 FE workflow.
* The WSAA ticket and the WSCT connection both use ARCA's service ID `wsct`.
  A ticket for `wsturiva` belongs to a different service and is rejected by
  WSCT.
* PyAfipWS WSCT formats its point-of-sale and document-type lists itself; the
  integration does not pass WSFE-only formatting arguments to those methods.
* The point-of-sale query includes a local workaround for PyAfipWS 3.10.3111's
  list/dictionary error parser defect; it does not alter PyAfipWS files.
* A live homologation test must be performed with an ARCA-enabled certificate,
  WSCT point of sale, document type, tourism code, and payment code before use
  in production.
