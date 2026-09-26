# Copyright 2026 Alfredo Sanz
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class _WsctGetCompat:
    """Keep the PyAfipWS 3.10.3111 dict-get typo inside this addon.

    That release calls both ``f.get(...)`` and ``f.get[...]`` while building
    the WSCT SOAP request.  The latter is a library defect.  Wrapping only the
    request dictionary makes both forms work without modifying the installed
    PyAfipWS package.
    """

    def __init__(self, values):
        self._values = values

    def __call__(self, *args, **kwargs):
        return dict.get(self._values, *args, **kwargs)

    def __getitem__(self, key):
        return dict.get(self._values, key)


class _WsctFacturaCompat(dict):
    @property
    def get(self):
        return _WsctGetCompat(self)


class AccountMove(models.Model):
    _inherit = "account.move"

    wsct_is_document = fields.Boolean(compute="_compute_wsct_is_document")
    wsct_net_amount = fields.Monetary(
        string="WSCT taxable net amount", compute="_compute_wsct_display_amounts",
    )
    wsct_informative_vat_amount = fields.Monetary(
        string="WSCT VAT 21%", compute="_compute_wsct_display_amounts",
    )
    wsct_reimbursement_amount = fields.Monetary(
        string="WSCT VAT reimbursement", compute="_compute_wsct_display_amounts",
    )
    wsct_gross_amount = fields.Monetary(
        string="WSCT subtotal including VAT", compute="_compute_wsct_display_amounts",
    )

    wsct_payment_code = fields.Char(
        string="WSCT payment method code",
        help="ARCA WSCT payment-method code. Obtain it from ConsultarFomasPago.",
    )
    wsct_payment_catalog_id = fields.Many2one(
        "wsct.catalog",
        string="WSCT payment method",
        domain=[("catalog_type", "=", "payment"), ("active", "=", True)],
    )
    wsct_fiscal_condition_catalog_id = fields.Many2one(
        "wsct.catalog",
        string="WSCT receiver fiscal condition",
        domain=[("catalog_type", "=", "fiscal_condition"), ("active", "=", True)],
    )
    wsct_card_type_catalog_id = fields.Many2one(
        "wsct.catalog",
        string="WSCT card type",
        domain=[("catalog_type", "=", "card_type"), ("active", "=", True)],
    )
    wsct_card_first_six = fields.Char(
        string="WSCT card first six digits",
        size=6,
        help="Enter only the first six digits; never enter the complete card number.",
    )
    wsct_relation_code = fields.Selection(
        [("1", "Accommodation directly to a non-resident tourist")],
        string="WSCT issuer/receiver relationship",
        default="1",
        required=True,
        readonly=True,
    )
    wsct_receiver_country_code = fields.Char(
        string="WSCT receiver country code",
        help="ARCA WSCT country code. If empty, the Argentine localization AFIP country code is used.",
    )
    wsct_receiver_tax_id = fields.Char(
        string="WSCT receiver tax ID",
        help="Foreign tax ID when required by WSCT.",
    )
    wsct_receiver_address = fields.Char(string="WSCT receiver address")
    wsct_observations = fields.Text(string="WSCT observations")
    wsct_same_foreign_currency = fields.Boolean(
        string="WSCT: payment in same foreign currency",
    )

    @api.depends("journal_id", "journal_id.afip_ws")
    def _compute_wsct_is_document(self):
        for move in self:
            move.wsct_is_document = move.journal_id.afip_ws == "wsct"

    @api.depends(
        "journal_id.afip_ws", "invoice_line_ids.display_type",
        "invoice_line_ids.price_subtotal",
    )
    def _compute_wsct_display_amounts(self):
        for move in self:
            net = sum(
                (line.price_subtotal for line in move.invoice_line_ids.filtered(
                    lambda line: line.display_type not in ("line_section", "line_note")
                )),
                0.0,
            )
            vat = move.currency_id.round(net * 0.21)
            move.wsct_net_amount = net if move.wsct_is_document else 0.0
            move.wsct_informative_vat_amount = vat if move.wsct_is_document else 0.0
            move.wsct_reimbursement_amount = -vat if move.wsct_is_document else 0.0
            move.wsct_gross_amount = net + vat if move.wsct_is_document else 0.0

    def _wsct_require(self, value, label):
        if value in (False, None, ""):
            raise UserError(_("WSCT requires %s.") % label)
        return value

    def _wsct_configured_taxes(self):
        self.ensure_one()
        journal = self.journal_id
        vat_tax = self._wsct_require(journal.wsct_vat_tax_id, _("the journal's WSCT VAT 21% tax"))
        reimbursement_tax = self._wsct_require(
            journal.wsct_reimbursement_tax_id,
            _("the journal's WSCT VAT reimbursement tax"),
        )
        if vat_tax.amount != 21 or reimbursement_tax.amount != -21:
            raise UserError(_("WSCT taxes must be configured as +21% VAT and -21% VAT reimbursement."))
        return vat_tax | reimbursement_tax

    def _wsct_apply_configured_taxes(self):
        for move in self.filtered("wsct_is_document"):
            taxes = move._wsct_configured_taxes()
            for line in move.invoice_line_ids.filtered(
                lambda item: item.display_type not in ("line_section", "line_note")
            ):
                line.tax_ids = [(6, 0, taxes.ids)]

    @api.onchange("journal_id", "invoice_line_ids")
    def _onchange_wsct_apply_configured_taxes(self):
        for move in self.filtered(
            lambda item: item.journal_id.afip_ws == "wsct"
            and item.journal_id.wsct_vat_tax_id
            and item.journal_id.wsct_reimbursement_tax_id
        ):
            move._wsct_apply_configured_taxes()

    def wsct_apply_native_taxes(self):
        """Apply the configured native VAT/reimbursement pair to draft lines."""
        for move in self:
            if move.state != "draft" or not move.wsct_is_document:
                raise UserError(_("Native WSCT taxes can only be applied to a draft Factura T."))
            move._wsct_apply_configured_taxes()
        return True

    def wsct_map_invoice_info(self):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("WSCT is only available for customer invoices and credit notes."))
        info = self.base_map_invoice_info()
        partner = self.commercial_partner_id
        country_code = self.wsct_receiver_country_code or partner.country_id.l10n_ar_afip_code
        self._wsct_require(country_code, _("the receiver country code"))
        self._wsct_require(self._wsct_payment_method_code(), _("the payment method"))
        self._wsct_require(self.wsct_fiscal_condition_catalog_id, _("the receiver fiscal condition"))
        self._wsct_require(self.l10n_latam_document_type_id.code, _("the ARCA document type"))

        info.update({
            # WSCT's XML schema uses an ISO date (YYYY-MM-DD), unlike WSFE.
            "fecha_cbte": str(self.invoice_date or fields.Date.today()),
            "cod_pais": country_code,
            "id_impositivo": self.wsct_fiscal_condition_catalog_id.code,
            "domicilio": self.wsct_receiver_address or self._wsct_partner_address(partner),
            "cod_relacion": self.wsct_relation_code,
            "observaciones": self.wsct_observations or "",
            "cancela_misma_moneda_ext": self.wsct_same_foreign_currency,
            **self._wsct_net_accounting_amounts(),
        })
        return info

    def _wsct_net_accounting_amounts(self):
        """Build WSCT's 21% VAT/reimbursement while Odoo books the net paid.

        A T invoice is recorded in Odoo without a VAT tax line: its total is
        the amount charged to the foreign tourist. WSCT still requires the
        notional 21% VAT subtotal and the exact negative reimbursement.
        """
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
        )
        self._wsct_require(lines, _("at least one invoice line"))
        net = sum((Decimal(str(line.price_subtotal)) for line in lines), Decimal("0"))
        vat = (net * Decimal("0.21")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        return {
            "imp_total": "%.2f" % self.amount_total,
            "imp_neto": "%.2f" % net,
            "imp_subtotal": "%.2f" % net,
            "imp_trib": "0.00",
            "imp_op_ex": "0.00",
            "imp_reintegro": "%.2f" % -vat,
            "wsct_vat_total": vat,
        }

    @staticmethod
    def _wsct_partner_address(partner):
        values = [partner.street, partner.street2, partner.zip, partner.city]
        address = ", ".join(value for value in values if value)
        if not address:
            raise UserError(_("WSCT requires the receiver address."))
        return address

    def wsct_pyafipws_create_invoice(self, ws, info):
        self.ensure_one()
        ws.CrearFactura(
            tipo_doc=info["tipo_doc"], nro_doc=info["nro_doc"],
            tipo_cbte=info["doc_afip_code"], punto_vta=info["pos_number"],
            cbte_nro=info["cbte_nro"], imp_total=info["imp_total"],
            imp_tot_conc=info["imp_tot_conc"], imp_neto=info["imp_neto"],
            imp_subtotal=info["imp_subtotal"], imp_trib=info["imp_trib"],
            imp_op_ex=info["imp_op_ex"], imp_reintegro=info["imp_reintegro"],
            fecha_cbte=info["fecha_cbte"], id_impositivo=info["id_impositivo"],
            cod_pais=info["cod_pais"], domicilio=info["domicilio"],
            cod_relacion=info["cod_relacion"], moneda_id=info["moneda_id"],
            moneda_ctz=info["moneda_ctz"], observaciones=info["observaciones"],
            cancela_misma_moneda_ext=info["cancela_misma_moneda_ext"],
        )

    def wsct_invoice_add_info(self, ws, info):
        self.ensure_one()
        if info["CbteAsoc"]:
            number = self._l10n_ar_get_document_number_parts(
                info["CbteAsoc"].l10n_latam_document_number,
                info["CbteAsoc"].l10n_latam_document_type_id.code,
            )
            ws.AgregarCmpAsoc(
                tipo=info["CbteAsoc"].l10n_latam_document_type_id.code,
                pto_vta=number["point_of_sale"], nro=number["invoice_number"],
            )
        amounts = self._wsct_net_accounting_amounts()
        ws.AgregarIva(5, amounts["imp_neto"], "%.2f" % amounts["wsct_vat_total"])
        self._wsct_add_items(ws)
        card_type = card_number = None
        if self._wsct_payment_is_card():
            card_type = self._wsct_require(self.wsct_card_type_catalog_id, _("the card type"))
            card_number = self._wsct_require(self.wsct_card_first_six, _("the first six card digits"))
            if len(card_number) != 6 or not card_number.isdigit():
                raise UserError(_("WSCT card first six digits must contain exactly six numbers."))
            card_type = card_type.code
        ws.AgregarFormaPago(
            codigo=self._wsct_payment_method_code(),
            tipo_tarjeta=card_type,
            numero_tarjeta=card_number,
        )

    def _wsct_payment_method_code(self):
        self.ensure_one()
        return self.wsct_payment_catalog_id.code or self.wsct_payment_code

    def _wsct_payment_is_card(self):
        self.ensure_one()
        description = (self.wsct_payment_catalog_id.name or "").lower()
        return self._wsct_payment_method_code() == "68" or "tarjeta" in description

    def wsct_refresh_card_types(self):
        """Load card types valid for the selected payment method from WSCT."""
        self.ensure_one()
        payment_code = self._wsct_require(self._wsct_payment_method_code(), _("the payment method"))
        ws = self.company_id.get_connection("wsct").connect()
        catalog = self.env["wsct.catalog"].sudo()
        for row in ws.ConsultarTiposTarjeta(payment_code, sep=None):
            values = {
                "catalog_type": "card_type",
                "code": str(row["codigo"]).strip(),
                "name": str(row.get("ds") or row.get("descripcion")).strip(),
                "active": True,
            }
            record = catalog.search([("catalog_type", "=", "card_type"), ("code", "=", values["code"])], limit=1)
            if record:
                record.write(values)
            else:
                catalog.create(values)
        return True

    def _wsct_add_items(self, ws):
        lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
        )
        if not lines:
            raise UserError(_("WSCT requires at least one invoice line."))
        for line in lines:
            product = line.product_id.product_tmpl_id
            tourism_code = product._wsct_tourism_service_code()
            self._wsct_require(tourism_code, _("the WSCT tourism service on each product"))
            self._wsct_require(line.product_id.default_code, _("an internal reference on each product"))
            line_net = Decimal(str(line.price_subtotal))
            vat_amount = (line_net * Decimal("0.21")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            ws.AgregarItem(
                tipo=product.wsct_item_type, cod_tur=tourism_code,
                codigo=line.product_id.default_code, ds=line.name,
                iva_id=5, imp_iva="%.2f" % vat_amount,
                imp_subtotal="%.2f" % (line_net + vat_amount),
            )

    def _check_argentinean_invoice_taxes(self):
        """Factura T uses the native +21%/-21% tax pair and remains net."""
        wsct_invoices = self.filtered("wsct_is_document")
        for invoice in wsct_invoices:
            taxes = invoice._wsct_configured_taxes()
            invalid_lines = invoice.invoice_line_ids.filtered(
                lambda line: line.display_type not in ("line_section", "line_note")
                and bool(taxes - line.tax_ids)
            )
            if invalid_lines:
                raise UserError(_("Every WSCT service line must include the configured VAT 21% and VAT reimbursement taxes."))
        return super(AccountMove, self - wsct_invoices)._check_argentinean_invoice_taxes()

    def wsct_request_autorization(self, ws):
        if isinstance(ws.factura, dict) and not isinstance(ws.factura, _WsctFacturaCompat):
            ws.factura = _WsctFacturaCompat(ws.factura)
        ws.CAESolicitar()
        # l10n_ar_afipws_fe expects YYYYMMDD; PyAfipWS WSCT returns YYYY/MM/DD.
        if ws.Vencimiento and "/" in ws.Vencimiento:
            ws.Vencimiento = datetime.strptime(ws.Vencimiento, "%Y/%m/%d").strftime("%Y%m%d")
