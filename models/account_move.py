from odoo import models, fields, api
from datetime import date

class Account(models.Model):
    _inherit = "account.move"

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

    # Help get reference number from sales order
    @api.onchange('invoice_origin')
    def _onchange_invoice_origin(self):
        for record in self:
            if record.invoice_origin:
                sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
                if sale_order:
                    record.x_reference_number = sale_order.name
                else:
                    record.x_reference_number = False
            else:
                record.x_reference_number = False   
