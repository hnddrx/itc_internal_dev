from odoo import models, fields, api

class Account(models.Model):
    _inherit = "account.move"

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
        help="Tax Identification Number of the customer associated with this account move."
    )

    x_reference_number = fields.Char(
        string="Reference Number",
        help="Reference number for this account move."
    )

    @api.model
    def create(self, vals):
        move = super().create(vals)
        if move.invoice_origin:
            sale_order = self.env['sale.order'].search(
                [('name', '=', move.invoice_origin)], limit=1
            )
            if sale_order:
                move.x_reference_number = sale_order.name
                move.x_invoice_type = sale_order.x_invoice_type or 'service'
        return move

