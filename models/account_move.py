from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    x_invoice_type = fields.Selection(
        [('service', 'Service'), ('consu', 'Sales')],
        string="Invoice Type",
        default='service',
    )

    x_partner_tin = fields.Char(
        string="Customer TIN",
        related='partner_id.vat',
        readonly=True,
        store=True,
    )

    x_reference_number = fields.Char(string="Reference Number", tracking=True)

    def _post(self, soft=True):
        for move in self:
            if move.move_type == 'out_invoice' and (not move.name or move.name == '/'):
                move.name = self.env['ir.sequence'].next_by_code('account.move.si') or 'New'
            elif move.move_type == 'in_invoice' and (not move.name or move.name == '/'):
                move.name = self.env['ir.sequence'].next_by_code('account.move.dv') or 'New'
        return super()._post(soft)

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