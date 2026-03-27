from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.modules.module import get_resource_path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
import io
import base64


class Account(models.Model):
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


    def _get_default_sequence_number(self):
        # Only override for customer/vendor invoices
        self.ensure_one()   
        if self.move_type == 'out_invoice':
            return self.env['ir.sequence'].next_by_code('account.move.si')
        elif self.move_type == 'in_invoice':
            return self.env['ir.sequence'].next_by_code('account.move.dv')
        return super()._get_default_sequence_number()

    @api.model
    def create(self, vals):
        self.payment_reference = self.name
        self.x_reference_number = self.name
        move = super().create(vals)
        
        if move.invoice_origin:
            sale_order = self.env['sale.order'].search(
                [('name', '=', move.invoice_origin)], limit=1
            )
            if sale_order:
                move.x_reference_number = sale_order.name
                move.x_invoice_type = sale_order.x_invoice_type or 'service'
        return move
