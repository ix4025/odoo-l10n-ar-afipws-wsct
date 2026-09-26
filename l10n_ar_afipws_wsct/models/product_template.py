from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    wsct_item_type = fields.Selection(
        [("0", "General"), ("99", "Reintegro / ajuste negativo")],
        string="WSCT item type",
        default="0",
        help="WSCT item type. Use 99 only for a reimbursement or negative adjustment.",
    )
    wsct_tourism_code = fields.Char(
        string="WSCT tourism code",
        help="ARCA WSCT tourism-service code. Obtain it from ConsultarCodigosItemTurismo.",
    )
    wsct_tourism_catalog_id = fields.Many2one(
        "wsct.catalog",
        string="WSCT tourism service",
        domain=[("catalog_type", "=", "tourism"), ("active", "=", True)],
    )

    def _wsct_tourism_service_code(self):
        self.ensure_one()
        return self.wsct_tourism_catalog_id.code or self.wsct_tourism_code
