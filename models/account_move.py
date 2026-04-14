from odoo import models, fields, api

from odoo.exceptions import ValidationError, UserError

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

    def get_2307_details(self):
        self.ensure_one()

        # only vendor bills
        if self.move_type != 'in_invoice':
            return []

        corp_dict = {}

        corp = self.company_id

        corp_dict[corp] = {
            'corporation': corp,
            'lines': [],
            'gross_amount': 0.0,
            'tax_withheld': 0.0,
            'net_amount': 0.0,
        }

        for line in self.invoice_line_ids:

            gross = line.price_subtotal or 0.0

            # ✅ correct tax extraction
            tax_amount = sum(t.amount for t in line.tax_ids)

            net = gross - tax_amount

            corp_entry = {
                'description': line.name or '',
                'atc': ', '.join(line.tax_ids.mapped('name')),
                'rate': sum(line.tax_ids.mapped('amount')),
                'month': self.invoice_date.month if self.invoice_date else False,
                'gross_amount': gross,
                'tax_withheld': abs(tax_amount),
                'net_amount': net,
                'tax_type': '',
                'payment_term': self.invoice_payment_term_id.name or '',
                'currency': self.currency_id.name,
                'conversion_rate': 1.0,
            }

            corp_dict[corp]['lines'].append(corp_entry)

            corp_dict[corp]['gross_amount'] += gross
            corp_dict[corp]['tax_withheld'] += abs(tax_amount)
            corp_dict[corp]['net_amount'] += net

        return list(corp_dict.values())

    def get_2307_business_details(self):
        """
        SAME mapping (you had 2 sections)
        """
        return self.get_2307_details()

    def action_print(self):
        self.ensure_one()

        if self.state != 'posted':
            raise UserError("Payment must be POSTED before generating BIR 2307.")

        return self.env.ref('itc_internal_dev.action_report_bir_2307').report_action(self)
