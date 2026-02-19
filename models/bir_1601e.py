from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date


class Bir1601E(models.Model):
    _name = "bir.1601e"
    _description = "BIR 1601-E Annual Return of Creditable Income Taxes Withheld (Expanded)"
    _rec_name = "display_name"
    _order = "year desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ================================
    # BASIC INFORMATION
    # ================================

    name = fields.Char(
        string="Reference",
        readonly=True,
        copy=False,
        index=True,
        default="New",
        help="Unique sequence number auto-assigned upon confirmation.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    year = fields.Integer(
        string="Year",
        required=True,
        default=date.today().year,
        tracking=True,
    )

    date_from = fields.Date(
        string="Date From",
        compute="_compute_dates",
        store=True,
    )

    date_to = fields.Date(
        string="Date To",
        compute="_compute_dates",
        store=True,
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    # ================================
    # WORKFLOW STATE
    # ================================

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("generated", "Generated"),
            ("confirmed", "Confirmed"),
            ("filed", "Filed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    date_confirmed = fields.Date(string="Date Confirmed", readonly=True, copy=False)
    date_filed = fields.Date(string="Date Filed", readonly=True, copy=False)
    confirmed_by = fields.Many2one("res.users", string="Confirmed By", readonly=True, copy=False)
    filed_by = fields.Many2one("res.users", string="Filed By", readonly=True, copy=False)

    # ================================
    # TAX COMPUTATION
    # ================================

    total_income_payments = fields.Float(
        string="Total Income Payments",
        digits=(16, 2),
        compute="_compute_totals_from_lines",
        store=True,
    )

    total_tax_required = fields.Float(
        string="Total Tax Required to be Withheld",
        digits=(16, 2),
        compute="_compute_totals_from_lines",
        store=True,
    )

    tax_previously_remitted = fields.Float(
        string="Tax Previously Remitted",
        digits=(16, 2),
        default=0.0,
    )

    # ---- Penalties ----
    surcharge = fields.Float(string="Surcharge", digits=(16, 2), default=0.0)
    interest = fields.Float(string="Interest", digits=(16, 2), default=0.0)
    compromise = fields.Float(string="Compromise", digits=(16, 2), default=0.0)

    # ---- Derived Totals ----
    total_tax_still_due = fields.Float(
        string="Total Tax Still Due",
        compute="_compute_derived_totals",
        store=True,
        digits=(16, 2),
    )

    total_penalties = fields.Float(
        string="Total Penalties",
        compute="_compute_derived_totals",
        store=True,
        digits=(16, 2),
    )

    total_amount_payable = fields.Float(
        string="Total Amount Payable",
        compute="_compute_derived_totals",
        store=True,
        digits=(16, 2),
    )

    # ================================
    # LINES
    # ================================

    line_ids = fields.One2many(
        "bir.1601e.line",
        "bir_id",
        string="Withholding Lines",
        copy=True,
    )

    # ================================
    # NOTES
    # ================================

    notes = fields.Text(string="Internal Notes")

    # =========================================
    # COMPUTES
    # =========================================

    @api.depends("year")
    def _compute_dates(self):
        for rec in self:
            if rec.year:
                rec.date_from = date(rec.year, 1, 1)
                rec.date_to = date(rec.year, 12, 31)
            else:
                rec.date_from = False
                rec.date_to = False

    @api.depends("name", "year", "company_id")
    def _compute_display_name(self):
        for rec in self:
            company_name = rec.company_id.name or ""
            seq = rec.name if rec.name and rec.name != "New" else "Draft"
            rec.display_name = f"1601-E | {company_name} | {rec.year} | {seq}"

    @api.depends("line_ids.tax_base", "line_ids.tax_withheld")
    def _compute_totals_from_lines(self):
        for rec in self:
            rec.total_income_payments = sum(rec.line_ids.mapped("tax_base"))
            rec.total_tax_required = sum(rec.line_ids.mapped("tax_withheld"))

    @api.depends(
        "total_tax_required",
        "tax_previously_remitted",
        "surcharge",
        "interest",
        "compromise",
    )
    def _compute_derived_totals(self):
        for rec in self:
            rec.total_tax_still_due = max(
                rec.total_tax_required - rec.tax_previously_remitted, 0.0
            )
            rec.total_penalties = rec.surcharge + rec.interest + rec.compromise
            rec.total_amount_payable = rec.total_tax_still_due + rec.total_penalties

    # ================================
    # CONSTRAINTS
    # ================================

    @api.constrains("year")
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > date.today().year + 1:
                raise ValidationError(
                    f"Year {rec.year} is not valid. "
                    f"Please enter a year between 2000 and {date.today().year + 1}."
                )

    _sql_constraints = [
        (
            "unique_company_year",
            "UNIQUE(company_id, year)",
            "A BIR 1601-E return for this company and year already exists.",
        )
    ]

    # ================================
    # SEQUENCE HELPERS
    # ================================

    def _get_sequence_code(self):
        """
        Returns the ir.sequence code used for this model.
        Must match the `code` defined in data/ir_sequence_data.xml.
        """
        return "bir.1601e"

    def _assign_sequence(self):
        """
        Consume the next sequence number and write it to `name`.
        Called on action_confirm so draft/generated records never
        consume a number — preventing gaps in the numbering series.
        """
        for rec in self:
            if rec.name == "New":
                rec.name = (
                    self.env["ir.sequence"].next_by_code(self._get_sequence_code())
                    or "New"
                )

    # ================================
    # STATE TRANSITIONS (WORKFLOW)
    # ================================

    def _check_editable(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(
                    "You can only modify a BIR 1601-E return in Draft state. "
                    "Reset to Draft first."
                )

    def _get_ewt_accounts(self, company_id):
        """
        Find all EWT/Withholding liability accounts directly from account.account.
        Searches by account name containing 'EWT' or 'Withholding' — no dependency
        on tax configuration, tax groups, or l10n_ph fields.
        This is the most reliable approach regardless of how taxes are named.
        """
        return self.env["account.account"].search([
            ("account_type", "in", ("liability_current", "liability_non_current")),
            "|",
            ("name", "ilike", "EWT"),
            ("name", "ilike", "Withholding"),
        ])

    def action_generate_data(self):
        """
        Generate withholding lines from posted vendor bill journal entries.
        Searches account.move.line directly by EWT/Withholding account name —
        no tax record lookup required.
        """
        self._check_editable()

        for rec in self:
            if not rec.company_id:
                raise ValidationError("Please select a Company before generating data.")
            if not rec.date_from or not rec.date_to:
                raise ValidationError("Year is not properly set.")

            rec.line_ids.unlink()

            # --- Find EWT accounts by name ---
            ewt_accounts = rec._get_ewt_accounts(rec.company_id.id)
            if not ewt_accounts:
                raise ValidationError(
                    "No Expanded Withholding Tax accounts found for this company. "
                    "Please ensure your Chart of Accounts has accounts with 'EWT' "
                    "or 'Withholding' in their name under current/non-current liabilities."
                )

            # --- Fetch posted journal lines on those accounts ---
            # CRITICAL: filter credit > 0 only — on a liability account,
            # credit = tax withheld (the actual EWT amount).
            # Debit lines on this account are base/gross payment reversals,
            # not tax — including them causes duplicate/wrong computation.
            move_lines = self.env["account.move.line"].search(
                [
                    ("date", ">=", rec.date_from),
                    ("date", "<=", rec.date_to),
                    ("account_id", "in", ewt_accounts.ids),
                    ("move_id.state", "=", "posted"),
                    ("company_id", "=", rec.company_id.id),
                    ("credit", ">", 0),
                ],
                order="date asc, move_id asc, id asc",
            )

            if not move_lines:
                raise ValidationError(
                    f"No posted Expanded Withholding Tax entries found for {rec.year}. "
                    "Please verify that vendor bills with EWT taxes have been posted "
                    "in the selected year, and that the EWT account is correctly assigned "
                    f"on those bills. Accounts searched: {', '.join(ewt_accounts.mapped('name'))}"
                )

            line_vals = []
            for ml in move_lines:
                # Credit on a liability account = tax withheld (always positive here)
                tax_withheld_amount = ml.credit
                atc_code, tax_rate = rec._resolve_atc(ml)

                tax_base = (
                    tax_withheld_amount / (tax_rate / 100.0)
                    if tax_rate
                    else tax_withheld_amount
                )

                line_vals.append({
                    "bir_id": rec.id,
                    "move_line_id": ml.id,
                    "date": ml.date,
                    "partner_id": ml.partner_id.id if ml.partner_id else False,
                    "nature_of_payment": (
                        ml.move_id.invoice_origin
                        or ml.move_id.ref
                        or ml.move_id.name
                        or "Income Payment"
                    ),
                    "atc": atc_code,
                    "tax_rate": tax_rate,
                    "tax_base": tax_base,
                })

            self.env["bir.1601e.line"].create(line_vals)

            rec.state = "generated"
            rec.message_post(
                body=(
                    f"Data generated: {len(line_vals)} withholding line(s) "
                    f"from accounts: {', '.join(ewt_accounts.mapped('name'))}."
                )
            )

    def _resolve_atc(self, move_line):
        """
        Resolve ATC code and tax rate from the linked account.tax record.
        Reads l10n_ph_atc directly if available (Odoo 18 l10n_ph).
        Falls back to _fallback_atc() by rate for manual entries.
        """
        tax = None
        if move_line.tax_line_id:
            tax = move_line.tax_line_id
        elif move_line.tax_ids:
            for t in move_line.tax_ids:
                if hasattr(t, 'l10n_ph_atc') and t.l10n_ph_atc:
                    tax = t
                    break
            if not tax:
                tax = move_line.tax_ids[0]

        if tax:
            rate = abs(tax.amount)
            atc = (
                tax.l10n_ph_atc
                if hasattr(tax, 'l10n_ph_atc') and tax.l10n_ph_atc
                else self._fallback_atc(rate)
            )
            return atc, rate

        return self._fallback_atc(2.0), 2.0

    def _fallback_atc(self, rate):
        """
        Fallback ATC lookup by rate when l10n_ph_atc is not set on the tax.
        Common EWT rates under TRAIN Law / RR 11-2018.
        """
        fallback = {
            1.0: "WI010",
            2.0: "WI010",
            5.0: "WI160",
            10.0: "WI158",
            15.0: "WI158",
            20.0: "WI340",
        }
        return fallback.get(rate, "WI010")


    def action_confirm(self):
        """
        Confirm the return.
        Sequence number is assigned HERE (not on creation) to avoid
        gaps caused by discarded draft records — an Odoo accounting best practice
        followed by account.move, purchase.order, etc.
        """
        for rec in self:
            if rec.state != "generated":
                raise UserError("Only a Generated return can be confirmed.")
            if not rec.line_ids:
                raise UserError(
                    "Cannot confirm a return with no withholding lines. "
                    "Please generate data first."
                )
            rec._assign_sequence()
            rec.state = "confirmed"
            rec.date_confirmed = date.today()
            rec.confirmed_by = self.env.user
            rec.message_post(
                body=f"Return confirmed by {self.env.user.name}. Reference: {rec.name}"
            )

    def action_file(self):
        """Mark the return as filed with the BIR."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError("Only a Confirmed return can be filed.")
            rec.state = "filed"
            rec.date_filed = date.today()
            rec.filed_by = self.env.user
            rec.message_post(
                body=f"Return [{rec.name}] filed with BIR by {self.env.user.name}."
            )

    def action_reset_to_draft(self):
        """
        Reset to Draft for corrections.
        The sequence number is intentionally RETAINED — it is never returned
        to the pool. This prevents gaps in the numbering series and preserves
        the audit trail, consistent with how Odoo handles vendor bills and
        sales orders.
        """
        for rec in self:
            if rec.state == "filed":
                raise UserError(
                    "A Filed return cannot be reset. "
                    "Please create an amended return if corrections are needed."
                )
            if rec.state == "cancelled":
                raise UserError("A Cancelled return cannot be reset to Draft.")
            rec.state = "draft"
            rec.date_confirmed = False
            rec.date_filed = False
            rec.confirmed_by = False
            rec.filed_by = False
            rec.message_post(body=f"Return [{rec.name}] reset to Draft.")

    def action_cancel(self):
        """Cancel the return (only from draft or generated)."""
        for rec in self:
            if rec.state in ("confirmed", "filed"):
                raise UserError(
                    "Cannot cancel a Confirmed or Filed return. "
                    "Contact your accounting manager."
                )
            rec.state = "cancelled"
            rec.message_post(body=f"Return [{rec.name}] cancelled.")

    # ================================
    # RECORD WRITE GUARD
    # ================================

    def write(self, vals):
        protected_fields = {
            "line_ids", "total_income_payments", "total_tax_required",
            "tax_previously_remitted", "surcharge", "interest", "compromise",
            "year", "company_id",
        }
        if any(f in vals for f in protected_fields):
            for rec in self:
                if rec.state not in ("draft", "generated"):
                    raise UserError(
                        f"Record '{rec.display_name}' is in '{rec.state}' state "
                        "and cannot be modified. Reset to Draft first."
                    )
        return super().write(vals)


# ============================================================


class Bir1601ELine(models.Model):
    _name = "bir.1601e.line"
    _description = "BIR 1601-E Withholding Tax Line"
    _order = "date asc, id asc"

    bir_id = fields.Many2one(
        "bir.1601e",
        string="BIR 1601-E",
        required=True,
        ondelete="cascade",
        index=True,
    )

    move_line_id = fields.Many2one(
        "account.move.line",
        string="Journal Item",
        ondelete="set null",
        readonly=True,
        help="Source journal item this line was generated from.",
    )

    date = fields.Date(string="Date", required=True, default=fields.Date.today)

    partner_id = fields.Many2one(
        "res.partner",
        string="Payee / Vendor",
        help="The income earner from whom tax was withheld.",
    )

    nature_of_payment = fields.Char(
        string="Nature of Income Payment",
        required=True,
    )

    atc = fields.Char(
        string="ATC",
        help="Alphanumeric Tax Code as defined by the BIR.",
    )

    tax_base = fields.Float(
        string="Tax Base (Gross Income)",
        digits=(16, 2),
        help="Gross amount of income payment subject to withholding.",
    )

    tax_rate = fields.Float(
        string="Tax Rate (%)",
        digits=(5, 2),
        default=2.0,
        help="Creditable withholding tax rate applied.",
    )

    tax_withheld = fields.Float(
        string="Tax Withheld",
        compute="_compute_tax_withheld",
        store=True,
        digits=(16, 2),
        help="Amount of tax withheld = Tax Base × Tax Rate / 100.",
    )

    company_id = fields.Many2one(
        related="bir_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    @api.depends("tax_base", "tax_rate")
    def _compute_tax_withheld(self):
        for rec in self:
            if rec.tax_rate and rec.tax_base:
                rec.tax_withheld = round(rec.tax_base * (rec.tax_rate / 100.0), 2)
            else:
                rec.tax_withheld = 0.0

    @api.constrains("tax_base", "tax_rate")
    def _check_positive_values(self):
        for rec in self:
            if rec.tax_base < 0:
                raise ValidationError(
                    f"Line '{rec.nature_of_payment}': Tax Base cannot be negative."
                )
            if rec.tax_rate < 0:
                raise ValidationError(
                    f"Line '{rec.nature_of_payment}': Tax Rate cannot be negative."
                )
