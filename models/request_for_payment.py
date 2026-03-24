import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Philippine VAT rate — update here if the rate ever changes.
_PH_VAT_RATE = 0.12


class RequestForPayment(models.Model):
    _name = 'request.for.payment'
    _description = 'Request for Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'id desc'

    # -------------------------------------------------------------------------
    # Identity / Header Fields
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='RFP Number',
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    rfp_date = fields.Date(
        string='RFP Date',
        default=fields.Date.context_today,
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Payment Party
    # -------------------------------------------------------------------------
    payee_type = fields.Selection(
        selection=[
            ('supplier', 'Supplier / Payee'),
            ('employee', 'Employee / Agent'),
        ],
        string='Payee Type',
        default='supplier',
        required=True,
        help='Choose whether the payment goes to an external supplier/payee '
             'or an internal employee/agent.',
    )
    supplier = fields.Many2one(
        comodel_name='res.partner',
        string='Supplier / Vendor',
        tracking=True,
        index=True,
    )
    employee = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        index=True,
    )

    # -------------------------------------------------------------------------
    # Approval / Signatories
    # -------------------------------------------------------------------------
    requested_by = fields.Many2one(
        comodel_name='res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    prepared_by = fields.Many2one(
        comodel_name='res.users',
        string='Prepared By',
        tracking=True,
    )
    noted_by = fields.Many2one(
        comodel_name='res.users',
        string='Noted By',
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Reference / Dates
    # -------------------------------------------------------------------------
    reference_number = fields.Char(
        string='Reference Number',
        copy=False,
        tracking=True,
        index=True,
    )
    reference_date = fields.Date(string='Reference Date', tracking=True)
    due_date = fields.Date(string='Due Date', tracking=True)
    remarks = fields.Text(string='Remarks')

    # -------------------------------------------------------------------------
    # Currency
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    currency_rate = fields.Float(
        string='Currency Rate',
        digits=(12, 6),
        default=1.0,
    )

    # -------------------------------------------------------------------------
    # Lines
    # -------------------------------------------------------------------------
    rfp_line_ids = fields.One2many(
        comodel_name='request.for.payment.line',
        inverse_name='rfp_id',
        string='Payment Details',
        copy=True,
    )

    # -------------------------------------------------------------------------
    # Totals
    # -------------------------------------------------------------------------
    amount_untaxed = fields.Monetary(
        string='Subtotal',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id',
        tracking=True,
    )
    tax_amount = fields.Monetary(
        string='VAT',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id',
        tracking=True,
    )
    amount_ewt = fields.Monetary(
        string='Total EWT',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id',
    )
    amount_net = fields.Monetary(
        string='Net Amount',
        store=True,
        compute='_compute_amounts',
        currency_field='currency_id',
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    @api.depends(
        'rfp_line_ids.untaxed_amount',
        'rfp_line_ids.tax_amount',
        'rfp_line_ids.ewt_amount',
        'rfp_line_ids.net_amount',
    )
    def _compute_amounts(self):
        for rfp in self:
            lines = rfp.rfp_line_ids
            rfp.amount_untaxed = sum(lines.mapped('untaxed_amount'))
            rfp.tax_amount     = sum(lines.mapped('tax_amount'))
            rfp.amount_ewt     = sum(lines.mapped('ewt_amount'))
            rfp.amount_net     = sum(lines.mapped('net_amount'))

    # -------------------------------------------------------------------------
    # ORM Overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('request.for.payment') or 'New'
                )
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Actions / Business Logic
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Duplicate PO Guard
    # -------------------------------------------------------------------------
    def _check_duplicate_approved_po(self):
        """
        Raise a UserError if any purchase order on this RFP's lines already
        appears in another *approved* RFP.

        Called from both action_submit (early warning) and action_approve
        (hard gate) so the user gets feedback as early as possible.
        """
        for rfp in self:
            # Collect POs referenced on this RFP (skip lines with no PO)
            po_ids = rfp.rfp_line_ids.mapped('purchase_order_id').filtered(bool)
            if not po_ids:
                continue

            # Find any OTHER approved RFP lines pointing to the same POs
            conflicting_lines = self.env['request.for.payment.line'].search([
                ('purchase_order_id', 'in', po_ids.ids),
                ('rfp_id.status', '=', 'approved'),
                ('rfp_id', '!=', rfp.id),
            ])

            if not conflicting_lines:
                continue

            # Build a human-readable conflict summary for the error message
            conflict_info = []
            for line in conflicting_lines:
                conflict_info.append(
                    '  • PO %s is already covered by approved RFP %s'
                    % (line.purchase_order_id.name, line.rfp_id.name)
                )

            raise UserError(
                'Cannot proceed — the following Purchase Orders already have '
                'an approved Request for Payment: %s' % ''.join(conflict_info)
                )

    def action_submit(self):
        for rfp in self:
            if rfp.status != 'draft':
                raise UserError("Only draft RFPs can be submitted.")
            if not rfp.rfp_line_ids:
                raise UserError(
                    "Please add at least one payment detail line before submitting."
                )
        # Early warning: flag duplicate POs before the record even leaves Draft
        self._check_duplicate_approved_po()
        self.write({'status': 'submitted'})

    def action_approve(self):
        for rfp in self:
            if rfp.status != 'submitted':
                raise UserError("Only submitted RFPs can be approved.")
        # Hard gate: re-check at approval in case another RFP was approved
        # in between submission and approval of this one
        self._check_duplicate_approved_po()
        self.write({'status': 'approved'})

    def action_reset_to_draft(self):
        for rfp in self:
            if rfp.status == 'approved':
                raise UserError("Approved RFPs cannot be reset to draft.")
        self.write({'status': 'draft'})

    # -------------------------------------------------------------------------
    # onchange — clear PO lines when supplier changes
    # -------------------------------------------------------------------------
    @api.onchange('supplier')
    def _onchange_supplier(self):
        """
        When the supplier on the header changes, clear any purchase_order_id
        on lines that belonged to the old supplier so the domain is not violated.
        """
        for line in self.rfp_line_ids:
            if line.purchase_order_id and line.purchase_order_id.partner_id != self.supplier:
                line.purchase_order_id = False


# =============================================================================
# LINE MODEL
# =============================================================================

class RequestForPaymentLine(models.Model):
    _name = 'request.for.payment.line'
    _description = 'Request for Payment Line'
    _order = 'sequence, id'

    rfp_id = fields.Many2one(
        comodel_name='request.for.payment',
        string='RFP Reference',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    currency_id = fields.Many2one(
        related='rfp_id.currency_id',
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Line Fields
    # -------------------------------------------------------------------------
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Purchase Order',
        index=True,
        domain="[('partner_id', '=', parent.supplier)]",
    )
    particulars = fields.Char(string='Particulars', required=True)

    vat_type = fields.Selection(
        selection=[
            ('vat_inclusive', 'VAT Inclusive'),
            ('vat_exclusive', 'VAT Exclusive'),
            ('vat_exempt', 'VAT Exempt'),
        ],
        string='VAT Type',
        default='vat_exclusive',
        required=True,
    )

    # ── Gross amount the user enters or that is auto-filled from the PO.
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
    )

    # ── VAT breakdown — computed from amount + vat_type, editable for overrides.
    untaxed_amount = fields.Monetary(
        string='Untaxed Amount',
        currency_field='currency_id',
        compute='_compute_vat_breakdown',
        store=True,
        readonly=False,
    )
    tax_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        compute='_compute_vat_breakdown',
        store=True,
        readonly=False,
    )

    # ── EWT
    ewt_code = fields.Many2one(
        comodel_name='account.tax',
        string='EWT Code',
        domain=[('type_tax_use', '=', 'purchase')],
    )
    rate = fields.Float(
        string='EWT Rate (%)',
        digits=(5, 2),
        compute='_compute_rate',
        store=True,
        readonly=False,
    )
    ewt_amount = fields.Monetary(
        string='EWT Amount',
        currency_field='currency_id',
        compute='_compute_ewt_amount',
        store=True,
        readonly=False,
    )
    net_amount = fields.Monetary(
        string='Net Amount',
        currency_field='currency_id',
        compute='_compute_net_amount',
        store=True,
        readonly=False,
    )

    # -------------------------------------------------------------------------
    # onchange — Purchase Order auto-fill
    # -------------------------------------------------------------------------
    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        """
        Auto-populate line fields when a Purchase Order is selected.

        Mapping:
          particulars  ← PO vendor reference (or PO name as fallback)
          vat_type     ← 'vat_inclusive' when the PO carries tax,
                         'vat_exempt'    when it does not
          amount       ← PO amount_total  (VAT-inclusive total)  when taxed
                         PO amount_untaxed (base total)           when exempt
        """
        for line in self:
            po = line.purchase_order_id
            if not po:
                continue

            line.particulars = po.partner_ref or po.name

            if po.amount_tax:
                line.vat_type = 'vat_inclusive'
                line.amount   = po.amount_total       # full VAT-inclusive total
            else:
                line.vat_type = 'vat_exempt'
                line.amount   = po.amount_untaxed     # no VAT, use base total

    # -------------------------------------------------------------------------
    # Compute — VAT breakdown
    # -------------------------------------------------------------------------
    @api.depends('amount', 'vat_type')
    def _compute_vat_breakdown(self):
        """
        Break the entered amount into untaxed base and VAT component.

        ┌─────────────────┬──────────────────────────────┬──────────────────┐
        │ vat_type        │ untaxed_amount                │ tax_amount       │
        ├─────────────────┼──────────────────────────────┼──────────────────┤
        │ vat_inclusive   │ amount / 1.12                 │ amount - untaxed │
        │ vat_exclusive   │ amount  (VAT excluded/outside)│ amount × 0.12    │
        │ vat_exempt      │ amount                        │ 0.00             │
        └─────────────────┴──────────────────────────────┴──────────────────┘

        VAT Exclusive means the entered amount is the pre-VAT base.
        The VAT figure is computed for BIR reporting but is NOT added
        to the payable net — the user is paying the base only.
        """
        for line in self:
            gross    = line.amount or 0.0
            vat_type = line.vat_type

            if vat_type == 'vat_inclusive':
                untaxed = gross / (1.0 + _PH_VAT_RATE)
                tax     = gross - untaxed
            elif vat_type == 'vat_exclusive':
                untaxed = gross
                tax     = gross * _PH_VAT_RATE
            else:  # vat_exempt
                untaxed = gross
                tax     = 0.0

            line.untaxed_amount = untaxed
            line.tax_amount     = tax

    # -------------------------------------------------------------------------
    # Compute — EWT
    # -------------------------------------------------------------------------
    @api.depends('ewt_code')
    def _compute_rate(self):
        for line in self:
            line.rate = abs(line.ewt_code.amount) if line.ewt_code else 0.0

    @api.depends('untaxed_amount', 'rate')
    def _compute_ewt_amount(self):
        """EWT is withheld on the untaxed base amount (BIR standard)."""
        for line in self:
            line.ewt_amount = line.untaxed_amount * (line.rate / 100.0)

    # -------------------------------------------------------------------------
    # Compute — Net Amount
    # -------------------------------------------------------------------------
    @api.depends('amount', 'vat_type', 'ewt_amount')
    def _compute_net_amount(self):
        """
        Net Amount = the cash actually released after EWT deduction.

        ┌─────────────────┬────────────────────────────────────────────────┐
        │ vat_type        │ net_amount formula                             │
        ├─────────────────┼────────────────────────────────────────────────┤
        │ vat_inclusive   │ amount − EWT                                   │
        │                 │ (VAT is already inside `amount`; we deduct EWT)│
        ├─────────────────┼────────────────────────────────────────────────┤
        │ vat_exclusive   │ amount − EWT                                   │
        │                 │ (VAT is EXCLUDED — not added to what you pay;  │
        │                 │  `amount` is the base, EWT is deducted from it)│
        ├─────────────────┼────────────────────────────────────────────────┤
        │ vat_exempt      │ amount − EWT                                   │
        └─────────────────┴────────────────────────────────────────────────┘
        """
        for line in self:
            line.net_amount = (line.amount or 0.0) - line.ewt_amount