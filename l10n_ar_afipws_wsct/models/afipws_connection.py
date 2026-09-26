# Copyright 2026 Alfredo Sanz
# SPDX-License-Identifier: AGPL-3.0-or-later

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AfipwsConnection(models.Model):
    _inherit = "afipws.connection"

    afip_ws = fields.Selection(
        selection_add=[("wsct", "Turismo - Comprobantes T (WSCT)")],
        ondelete={"wsct": "set default"},
    )

    @api.model
    def _get_ws(self, afip_ws):
        ws = super()._get_ws(afip_ws)
        if afip_ws == "wsct":
            try:
                from pyafipws.wsct import WSCT
            except ImportError as error:
                raise UserError(
                    _("PyAfipWS with WSCT support is required: %s") % error
                ) from error
            ws = WSCT()
        return ws

    @api.model
    def get_afip_ws_url(self, afip_ws, environment_type):
        url = super().get_afip_ws_url(afip_ws, environment_type)
        if url or afip_ws != "wsct":
            return url
        if environment_type == "homologation":
            return "https://fwshomo.afip.gov.ar/wsct/CTService?wsdl"
        if environment_type == "production":
            return "https://serviciosjava.afip.gob.ar/wsct/CTService?wsdl"
        raise UserError(_("Unknown AFIP environment: %s") % environment_type)
