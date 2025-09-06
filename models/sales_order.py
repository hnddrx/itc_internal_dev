from odoo import models, fields, api
from datetime import date

class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_invoice_type = fields.Selection(
        [
            ('service', 'Service'),
            ('consu', 'Sales'),
        ],
        string="Invoice Type",
        default='service',
        help="Indicates whether the invoice is Service or Sales."
    )

    x_partner_tin = fields.Char(
        string="Customer TIN",
        related='partner_id.vat',
        readonly=True,
        store=True,
        help="Tax Identification Number of the customer associated with this sales order."
    )       