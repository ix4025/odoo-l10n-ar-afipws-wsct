from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    wsct_vat_tax_id = fields.Many2one(
        "account.tax",
        string="WSCT VAT 21% tax",
        domain=[("type_tax_use", "=", "sale")],
        help="Native 21% sales tax shown on a Factura T invoice.",
    )
    wsct_reimbursement_tax_id = fields.Many2one(
        "account.tax",
        string="WSCT VAT reimbursement tax",
        domain=[("type_tax_use", "=", "sale")],
        help="Native -21% sales tax posted to the VAT reimbursement asset account.",
    )

    def _get_afip_ws(self):
        values = super()._get_afip_ws()
        return values + [("wsct", _("Tourism vouchers - Factura T (WSCT)"))]

    def _get_l10n_ar_afip_pos_types_selection(self):
        values = super()._get_l10n_ar_afip_pos_types_selection()
        return values + [("WSCT", _("Tourism vouchers - Factura T (WSCT)"))]

    @api.model
    def _get_type_mapping(self):
        values = dict(super()._get_type_mapping())
        values["WSCT"] = "wsct"
        return values

    def _get_journal_letter(self, counterpart_partner=False):
        """WSCT documents are always class T, irrespective of the partner."""
        self.ensure_one()
        if self.l10n_ar_afip_pos_system == "WSCT":
            return ["T"]
        return super()._get_journal_letter(counterpart_partner=counterpart_partner)

    def _get_journal_codes_domain(self):
        """Allow WSCT's ARCA types in Odoo's document-type selector."""
        self.ensure_one()
        if self.l10n_ar_afip_pos_system == "WSCT":
            return [("code", "in", ["195", "196", "197"])]
        return super()._get_journal_codes_domain()

    def wsct_get_pyafipws_last_invoice(self, pos_number, document_type, ws):
        self.ensure_one()
        if not document_type or not document_type.code:
            raise UserError(_("A document type with an ARCA code is required for WSCT."))
        return ws.ConsultarUltimoComprobanteAutorizado(document_type.code, pos_number)

    def wsct_pyafipws_point_of_sales(self, ws):
        """Read WSCT points without the PyAfipWS list/dict defect.

        PyAfipWS 3.10.3111 initializes ``ret`` as a list and immediately
        passes it to an internal error parser that expects a dictionary. This
        uses the same WSCT SOAP operation directly, preserving PyAfipWS itself.
        """
        response = ws.client.consultarPuntosVenta(
            authRequest={
                "token": ws.Token,
                "sign": ws.Sign,
                "cuitRepresentada": ws.Cuit,
            },
        ).get("consultarPuntosVentaReturn", {})
        errors = []
        for key in ("arrayErrores", "arrayErroresFormato"):
            values = response.get(key, []) or []
            if isinstance(values, dict):
                values = [values]
            for value in values:
                detail = (
                    value.get("codigoDescripcion")
                    or value.get("codigoDescripcionString")
                    or {}
                )
                errors.append(
                    "%s: %s" % (
                        detail.get("codigo", ""),
                        detail.get("descripcion", ""),
                    )
                )
        ws.ErrMsg = "\n".join(error for error in errors if error != ": ")

        points = response.get("arrayPuntosVenta", []) or []
        if isinstance(points, dict):
            points = [points]
        return [
            "%s: bloqueado=%s baja=%s"
            % (
                item.get("puntoVenta", item).get("numeroPuntoVenta", ""),
                item.get("puntoVenta", item).get("bloqueado", ""),
                item.get("puntoVenta", item).get("fechaBaja", ""),
            )
            for item in points
        ]

    def wsct_pyafipws_cuit_document_classes(self, ws):
        # PyAfipWS WSCT returns a list of already formatted descriptions and
        # does not accept the optional ``sep`` used by some other services.
        return ws.ConsultarTiposComprobante()

    def wsct_refresh_catalogs(self):
        """Refresh WSCT reference values without modifying existing invoices."""
        self.ensure_one()
        if self.afip_ws != "wsct":
            raise UserError(_("This action is only available for a WSCT journal."))
        ws = self.company_id.get_connection("wsct").connect()
        catalog = self.env["wsct.catalog"].sudo()
        sources = (
            ("tourism", ws.ConsultarCodigosItemTurismo()),
            ("payment", ws.ConsultarFomasPago(sep=None)),
            ("fiscal_condition", ws.ConsultarCondicionesIVA()),
        )
        count = 0
        for catalog_type, rows in sources:
            for row in rows:
                if isinstance(row, str):
                    code, name = row.split(":", 1)
                else:
                    code, name = row["codigo"], row.get("ds") or row.get("descripcion")
                values = {"catalog_type": catalog_type, "code": str(code).strip(), "name": str(name).strip(), "active": True}
                record = catalog.search([("catalog_type", "=", catalog_type), ("code", "=", values["code"])], limit=1)
                if record:
                    record.write(values)
                else:
                    catalog.create(values)
                count += 1
        self.message_post(body=Markup(_("WSCT catalogs updated: %s records received.") % count))
        return True

    def get_pyafipws_post_invoice_numbers(self):
        """Show the next WSCT number without assuming WSFE's CSV format."""
        wsct_journals = self.filtered(lambda journal: journal.afip_ws == "wsct")
        other_journals = self - wsct_journals
        result = super(AccountJournal, other_journals).get_pyafipws_post_invoice_numbers()
        for journal in wsct_journals:
            ws = journal.company_id.get_connection("wsct").connect()
            messages = []
            for row in ws.ConsultarTiposComprobante():
                code, description = row.split(":", 1)
                last = ws.ConsultarUltimoComprobanteAutorizado(
                    int(code.strip()), journal.l10n_ar_afip_pos_number
                )
                messages.append(
                    "%s %05d-%08d"
                    % (description.strip(), journal.l10n_ar_afip_pos_number, int(last) + 1)
                )
            journal.message_post(body=Markup("<br/>\n").join(messages))
        return result
