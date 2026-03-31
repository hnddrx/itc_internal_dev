from odoo import api, fields, models, _

class AccountPayment(models.Model):
    _inherit = "account.payment"

    expense_type = fields.Many2one(
        'product.template',
        string="Expense Type",
        domain=[('can_be_expensed', '=', True)]
    )

    
    # ------------------------------------------------------------------
    # Fields stored on the posted payment
    # ------------------------------------------------------------------
    payment_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Payment Tax',
        copy=False,
    )
    payment_base_amount = fields.Monetary(
        string='Base Amount (excl. Tax)',
        currency_field='currency_id',
        copy=False,
    )
    payment_tax_amount = fields.Monetary(
        string='Tax Amount',
        currency_field='currency_id',
        copy=False,
    )
 
    # ------------------------------------------------------------------
    # Override: inject tax lines into the journal entry move lines
    # ------------------------------------------------------------------
    """ def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None, **kwargs):
    
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
            **kwargs,
        )
 
        if not self.payment_tax_id or len(line_vals_list) < 2:
            return line_vals_list
 
        tax = self.payment_tax_id
        currency = self.currency_id
 
        taxes_res = tax.compute_all(
            price_unit=self.amount,
            currency=currency,
            quantity=1.0,
            partner=self.partner_id or None,
        )
 
        base_amount = taxes_res['total_excluded']
        total_amount = taxes_res['total_included']
        tax_lines_data = taxes_res.get('taxes', [])
 
        if not tax_lines_data:
            return line_vals_list
 
        # line_vals_list[0] = liquidity line (bank/cash)
        # line_vals_list[1] = counterpart line (AR/AP outstanding)
        liquidity_line = line_vals_list[0]
        counterpart_line = line_vals_list[1]
 
        sign = 1 if self.payment_type == 'inbound' else -1
 
        # Adjust liquidity line to full total (base + tax)
        if liquidity_line.get('debit', 0.0):
            liquidity_line['debit'] = total_amount
            liquidity_line['credit'] = 0.0
        else:
            liquidity_line['credit'] = total_amount
            liquidity_line['debit'] = 0.0
        liquidity_line['amount_currency'] = sign * total_amount
 
        # Adjust counterpart line to base only
        if counterpart_line.get('debit', 0.0):
            counterpart_line['debit'] = base_amount
            counterpart_line['credit'] = 0.0
        else:
            counterpart_line['credit'] = base_amount
            counterpart_line['debit'] = 0.0
        counterpart_line['amount_currency'] = -sign * base_amount
 
        # Add one line per tax component
        for tax_data in tax_lines_data:
            tax_amount = abs(tax_data['amount'])
            if not tax_amount:
                continue
 
            # Resolve tax account from compute_all result first,
            # then fall back to the tax's repartition lines
            tax_account_id = tax_data.get('account_id')
            if not tax_account_id:
                repartition = self.env['account.tax.repartition.line'].search([
                    ('tax_id', '=', tax_data['id']),
                    ('repartition_type', '=', 'tax'),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                tax_account_id = (
                    repartition.account_id.id
                    if repartition and repartition.account_id
                    else counterpart_line.get('account_id')
                )
 
            # inbound: tax credited (liability); outbound: tax debited (expense/asset)
            if self.payment_type == 'inbound':
                tax_debit, tax_credit = 0.0, tax_amount
                tax_amount_currency = -tax_amount
            else:
                tax_debit, tax_credit = tax_amount, 0.0
                tax_amount_currency = tax_amount
 
            line_vals_list.append({
                'name': tax_data.get('name', tax.name),
                'account_id': tax_account_id,
                'debit': tax_debit,
                'credit': tax_credit,
                'amount_currency': tax_amount_currency,
                'currency_id': currency.id,
                'partner_id': self.partner_id.id if self.partner_id else False,
                'tax_base_amount': base_amount,
                'tax_repartition_line_id': tax_data.get('tax_repartition_line_id'),
                'tax_ids': [],
                'tax_tag_ids': tax_data.get('tag_ids', []),
            })
 
        return line_vals_list """
 
    # ------------------------------------------------------------------
    # Log tax summary to chatter on post
    # ------------------------------------------------------------------
    """ def action_post(self):
        res = super().action_post()
        for payment in self.filtered('payment_tax_id'):
            payment.message_post(body=_(
                "Tax applied: %(tax)s — Base: %(base)s, Tax: %(tax_amt)s %(currency)s",
                tax=payment.payment_tax_id.name,
                base=payment.payment_base_amount,
                tax_amt=payment.payment_tax_amount,
                currency=payment.currency_id.name,
            ))
        return res
    """


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Tax',
        domain=[('type_tax_use', 'in', ['sale', 'purchase', 'none'])],
    )
    tax_amount = fields.Monetary(
        string='Tax Amount',
        compute='_compute_tax_breakdown',
        currency_field='currency_id',
    )
    base_amount = fields.Monetary(
        string='Base Amount',
        compute='_compute_tax_breakdown',
        currency_field='currency_id',
    )
    total_with_tax = fields.Monetary(
        string='Total (incl. Tax)',
        compute='_compute_tax_breakdown',
        currency_field='currency_id',
    )
    tax_breakdown_ids = fields.One2many(
        comodel_name='account.payment.register.tax.line',
        inverse_name='wizard_id',
        string='Tax Breakdown',
        compute='_compute_tax_breakdown',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    """ @api.depends('amount', 'tax_id', 'currency_id', 'partner_id')
    def _compute_tax_breakdown(self):
        TaxLine = self.env['account.payment.register.tax.line']
        for wizard in self:
            wizard.tax_breakdown_ids = TaxLine
            wizard.tax_amount = 0.0
            wizard.base_amount = wizard.amount
            wizard.total_with_tax = wizard.amount

            if not wizard.tax_id or not wizard.amount:
                continue

            currency = wizard.currency_id or self.env.company.currency_id
            taxes_res = wizard.tax_id.compute_all(
                price_unit=wizard.amount,
                currency=currency,
                quantity=1.0,
                partner=wizard.partner_id or None,
            )

            wizard.base_amount = taxes_res['total_excluded']
            wizard.total_with_tax = taxes_res['total_included']
            wizard.tax_amount = wizard.total_with_tax - wizard.base_amount

            lines = TaxLine
            for t in taxes_res.get('taxes', []):
                lines |= TaxLine.new({
                    'wizard_id': wizard.id,
                    'tax_id': t['id'],
                    'name': t['name'],
                    'base': t['base'],
                    'amount': t['amount'],
                    'account_id': t.get('account_id') or False,
                })
            wizard.tax_breakdown_ids = lines """

    # ------------------------------------------------------------------
    # Override: pass tax data into payment vals
    # ------------------------------------------------------------------
    """ def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.tax_id:
            vals['payment_tax_id'] = self.tax_id.id
            vals['payment_base_amount'] = self.base_amount
            vals['payment_tax_amount'] = self.tax_amount
        return vals
 """

class AccountPaymentRegisterTaxLine(models.TransientModel):
    _name = 'account.payment.register.tax.line'
    _description = 'Payment Register Tax Breakdown Line'

    wizard_id = fields.Many2one(
        comodel_name='account.payment.register',
        required=True,
        ondelete='cascade',
    )
    tax_id = fields.Many2one('account.tax', string='Tax')
    name = fields.Char(string='Tax Name')
    base = fields.Monetary(string='Base Amount', currency_field='currency_id')
    amount = fields.Monetary(string='Tax Amount', currency_field='currency_id')
    account_id = fields.Many2one('account.account', string='Tax Account')
    currency_id = fields.Many2one(related='wizard_id.currency_id')