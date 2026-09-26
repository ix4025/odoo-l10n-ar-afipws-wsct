# Copyright 2026 Alfredo Sanz
# SPDX-License-Identifier: AGPL-3.0-or-later

from odoo import api, fields, models


class WsctCatalog(models.Model):
    _name = "wsct.catalog"
    _description = "ARCA WSCT catalog"
    _order = "catalog_type, code"
    _rec_name = "label"

    catalog_type = fields.Selection(
        [
            ("payment", "Payment method"),
            ("tourism", "Tourism service"),
            ("fiscal_condition", "Fiscal condition"),
            ("card_type", "Card type"),
        ],
        required=True,
        index=True,
    )
    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    label = fields.Char(compute="_compute_label", store=True, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("wsct_catalog_type_code_uniq", "unique(catalog_type, code)", "WSCT code must be unique per catalog."),
    ]

    @api.depends("code", "name")
    def _compute_label(self):
        for record in self:
            record.label = "%s - %s" % (record.code or "", record.name or "")
