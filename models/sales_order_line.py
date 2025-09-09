from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


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

    x_unit_price_usd = fields.Float(
        string="Unit Price (USD)",
        digits="Product Price",
        compute="_compute_unit_price_usd",
        inverse="_inverse_unit_price_usd",
        store=True,
        help="Unit price in USD for this sales order line.",
    )

    x_gain_loss = fields.Float(
        string="FX Gain/Loss (USD)",
        compute="_compute_gain_loss",
        store=True,
        help="Difference between expected USD and actual USD conversion.",
    )

    @api.depends("price_unit", "order_id.x_conversion_rate")
    def _compute_unit_price_usd(self):
        for line in self:
            rate = line.order_id.x_conversion_rate or 1.0
            line.x_unit_price_usd = line.price_unit / rate

    def _inverse_unit_price_usd(self):
        for line in self:
            rate = line.order_id.x_conversion_rate or 1.0
            line.price_unit = line.x_unit_price_usd * rate

    @api.depends("planned_rate", "actual_rate", "price_unit")
    def _compute_gain_loss(self):
        for line in self:
            if line.planned_rate and line.actual_rate:
                expected = line.price_unit / line.planned_rate
                actual = line.price_unit / line.actual_rate
                line.x_gain_loss = actual - expected
            else:
                line.x_gain_loss = 0.0
