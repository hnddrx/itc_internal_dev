from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="The currency used for this sales order.",
        readonly=False
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="The company associated with this sales order.",
        readonly=True
    )

    x_conversion_rate = fields.Float(
        string="Conversion Rate",
        digits=(12, 6),
        compute="_compute_conversion_rate",
        store=True,
        readonly=False,
        help="The conversion rate from the selected currency to the company's base currency (PHP)."
    )

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

    x_remarks = fields.Text(
        string="Remarks",
        help="Remarks related to this sales order."
    )

    
    planned_rate = fields.Float(
        string="Planned Rate (PHP per USD)",
        digits=(12, 6),
        help="Budgeted or expected conversion rate.",
    )

    actual_rate = fields.Float(
        string="Actual Rate (PHP per USD)",
        digits=(12, 6),
        help="Actual conversion rate at transaction/payment time.",
    )


    @api.depends('currency_id', 'date_order', 'company_id')
    def _compute_conversion_rate(self):
        """Always compute conversion rate based on currency and date."""
        for order in self:
            if order.currency_id and order.company_id.currency_id:
                company_currency = order.company_id.currency_id
                order_currency = order.currency_id
                order_date = order.date_order or fields.Date.today()

                # Fetch rate for the selected currency
                rate = order_currency._get_rates(
                    company=order.company_id,
                    date=order_date
                ).get(order_currency.id)

                order.x_conversion_rate = rate or 1.0
            else:
                order.x_conversion_rate = 1.0
