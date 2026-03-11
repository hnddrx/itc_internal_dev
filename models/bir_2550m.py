from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import date
import calendar


# ============================================================
# SCHEDULE LINE MODELS
# ============================================================

class Bir2550mSch1Line(models.Model):
    """Schedule 1 - Sales/Receipts and Output Tax"""
    _name = "bir.2550m.sch1"
    _description = "2550M Schedule 1 - Vatable Sales"
    _order = "sequence, id"

    bir_id       = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    sequence     = fields.Integer(default=10)
    industry     = fields.Char(string="Industries Covered by VAT", required=True)
    atc          = fields.Char(string="ATC")
    sales_amount = fields.Monetary(string="Amount of Sales/Receipts", currency_field="currency_id")
    output_tax   = fields.Monetary(string="Output Tax",               currency_field="currency_id",
                                   compute="_compute_output_tax", store=True)
    currency_id  = fields.Many2one(related="bir_id.currency_id", store=True)

    @api.depends("sales_amount")
    def _compute_output_tax(self):
        for rec in self:
            rec.output_tax = round(rec.sales_amount * 0.12, 2)


class Bir2550mSch2Line(models.Model):
    """Schedule 2 - Capital Goods ≤ ₱1M"""
    _name = "bir.2550m.sch2"
    _description = "2550M Schedule 2 - Capital Goods ≤ P1M"
    _order = "date_purchased, id"

    bir_id          = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    date_purchased  = fields.Date(string="Date Purchased")
    description     = fields.Char(string="Description")
    amount          = fields.Monetary(string="Amount (Net of VAT)", currency_field="currency_id")
    input_tax       = fields.Monetary(string="Input Tax",           currency_field="currency_id",
                                      compute="_compute_input_tax", store=True)
    currency_id     = fields.Many2one(related="bir_id.currency_id", store=True)

    @api.depends("amount")
    def _compute_input_tax(self):
        for rec in self:
            rec.input_tax = round(rec.amount * 0.12, 2)


class Bir2550mSch3Line(models.Model):
    """Schedule 3 - Capital Goods > ₱1M"""
    _name = "bir.2550m.sch3"
    _description = "2550M Schedule 3 - Capital Goods > P1M"
    _order = "date_purchased, id"

    bir_id             = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    # A) Current Period Purchases
    is_previous_period = fields.Boolean(string="Previous Period", default=False,
                                        help="Check if this is a previous period purchase carried over.")
    date_purchased     = fields.Date(string="Date Purchased")
    description        = fields.Char(string="Description")
    amount             = fields.Monetary(string="Amount (Net of VAT)", currency_field="currency_id")
    input_tax          = fields.Monetary(string="Input Tax (C×12%)",   currency_field="currency_id",
                                         compute="_compute_input_tax", store=True)
    est_life_months    = fields.Integer(string="Est. Life (months)")
    recognized_life    = fields.Integer(string="Recognized Life (months)",
                                        compute="_compute_recognized_life", store=True)
    allowable_input_tax = fields.Monetary(string="Allowable Input Tax (Period)",
                                          compute="_compute_allowable", store=True,
                                          currency_field="currency_id")
    balance_input_tax   = fields.Monetary(string="Balance of Input Tax (Next Period)",
                                          compute="_compute_allowable", store=True,
                                          currency_field="currency_id")
    currency_id         = fields.Many2one(related="bir_id.currency_id", store=True)

    @api.depends("amount")
    def _compute_input_tax(self):
        for rec in self:
            rec.input_tax = round(rec.amount * 0.12, 2)

    @api.depends("est_life_months")
    def _compute_recognized_life(self):
        for rec in self:
            rec.recognized_life = min(rec.est_life_months, 60) if rec.est_life_months else 0

    @api.depends("input_tax", "recognized_life")
    def _compute_allowable(self):
        for rec in self:
            if rec.recognized_life:
                rec.allowable_input_tax = round(rec.input_tax / rec.recognized_life, 2)
            else:
                rec.allowable_input_tax = 0.0
            rec.balance_input_tax = rec.input_tax - rec.allowable_input_tax


class Bir2550mSch4Line(models.Model):
    """Schedule 4 - Input Tax Attributable to Sale to Government"""
    _name = "bir.2550m.sch4"
    _description = "2550M Schedule 4 - Input Tax on Sales to Government"
    _order = "id"

    bir_id                = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    input_tax_direct      = fields.Monetary(string="Input Tax Directly Attributable to Govt Sales",
                                            currency_field="currency_id")
    taxable_sales_govt    = fields.Monetary(string="Taxable Sales to Government", currency_field="currency_id")
    total_sales           = fields.Monetary(string="Total Sales",                 currency_field="currency_id")
    input_tax_not_direct  = fields.Monetary(string="Input Tax Not Directly Attributable",
                                            currency_field="currency_id")
    ratable_portion       = fields.Monetary(string="Ratable Portion",
                                            compute="_compute_ratable", store=True,
                                            currency_field="currency_id")
    total_input_tax       = fields.Monetary(string="Total Input Tax Attributable to Govt",
                                            compute="_compute_total", store=True,
                                            currency_field="currency_id")
    standard_input_tax    = fields.Monetary(string="Less: Standard Input Tax to Govt",
                                            currency_field="currency_id")
    closed_to_expense     = fields.Monetary(string="Input Tax Closed to Expense (→ Item 20B)",
                                            compute="_compute_closed", store=True,
                                            currency_field="currency_id")
    currency_id           = fields.Many2one(related="bir_id.currency_id", store=True)

    @api.depends("taxable_sales_govt", "total_sales", "input_tax_not_direct")
    def _compute_ratable(self):
        for rec in self:
            if rec.total_sales:
                rec.ratable_portion = round(
                    (rec.taxable_sales_govt / rec.total_sales) * rec.input_tax_not_direct, 2
                )
            else:
                rec.ratable_portion = 0.0

    @api.depends("input_tax_direct", "ratable_portion")
    def _compute_total(self):
        for rec in self:
            rec.total_input_tax = rec.input_tax_direct + rec.ratable_portion

    @api.depends("total_input_tax", "standard_input_tax")
    def _compute_closed(self):
        for rec in self:
            rec.closed_to_expense = rec.total_input_tax - rec.standard_input_tax


class Bir2550mSch5Line(models.Model):
    """Schedule 5 - Input Tax Attributable to Exempt Sales"""
    _name = "bir.2550m.sch5"
    _description = "2550M Schedule 5 - Input Tax on Exempt Sales"
    _order = "id"

    bir_id               = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    input_tax_direct     = fields.Monetary(string="Input Tax Directly Attributable to Exempt Sales",
                                           currency_field="currency_id")
    taxable_exempt_sale  = fields.Monetary(string="Taxable Exempt Sale",           currency_field="currency_id")
    total_sales          = fields.Monetary(string="Total Sales",                   currency_field="currency_id")
    input_tax_not_direct = fields.Monetary(string="Input Tax Not Directly Attributable",
                                           currency_field="currency_id")
    ratable_portion      = fields.Monetary(string="Ratable Portion",
                                           compute="_compute_ratable", store=True,
                                           currency_field="currency_id")
    total_allocable      = fields.Monetary(string="Total Input Tax Allocable to Exempt (→ Item 20C)",
                                           compute="_compute_total", store=True,
                                           currency_field="currency_id")
    currency_id          = fields.Many2one(related="bir_id.currency_id", store=True)

    @api.depends("taxable_exempt_sale", "total_sales", "input_tax_not_direct")
    def _compute_ratable(self):
        for rec in self:
            if rec.total_sales:
                rec.ratable_portion = round(
                    (rec.taxable_exempt_sale / rec.total_sales) * rec.input_tax_not_direct, 2
                )
            else:
                rec.ratable_portion = 0.0

    @api.depends("input_tax_direct", "ratable_portion")
    def _compute_total(self):
        for rec in self:
            rec.total_allocable = rec.input_tax_direct + rec.ratable_portion


class Bir2550mSch6Line(models.Model):
    """Schedule 6 - Creditable VAT Withheld (Tax Credit)"""
    _name = "bir.2550m.sch6"
    _description = "2550M Schedule 6 - Creditable VAT Withheld"
    _order = "id"

    bir_id              = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    period_covered      = fields.Char(string="Period Covered")
    withholding_agent   = fields.Char(string="Name of Withholding Agent")
    income_payment      = fields.Monetary(string="Income Payment",      currency_field="currency_id")
    total_tax_withheld  = fields.Monetary(string="Total Tax Withheld",  currency_field="currency_id")
    applied_current_mo  = fields.Monetary(string="Applied - Current Mo.",currency_field="currency_id")
    currency_id         = fields.Many2one(related="bir_id.currency_id", store=True)


class Bir2550mSch7Line(models.Model):
    """Schedule 7 - Advance Payments for Sugar and Flour"""
    _name = "bir.2550m.sch7"
    _description = "2550M Schedule 7 - Advance Payments (Sugar/Flour)"
    _order = "id"

    bir_id             = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    period_covered     = fields.Char(string="Period Covered")
    miller_name        = fields.Char(string="Name of Miller")
    taxpayer_name      = fields.Char(string="Name of Taxpayer")
    or_number          = fields.Char(string="Official Receipt Number")
    amount_paid        = fields.Monetary(string="Amount Paid",          currency_field="currency_id")
    applied_current_mo = fields.Monetary(string="Applied - Current Mo.",currency_field="currency_id")
    currency_id        = fields.Many2one(related="bir_id.currency_id", store=True)


class Bir2550mSch8Line(models.Model):
    """Schedule 8 - VAT Withheld on Sales to Government"""
    _name = "bir.2550m.sch8"
    _description = "2550M Schedule 8 - VAT Withheld on Govt Sales"
    _order = "id"

    bir_id             = fields.Many2one("bir.2550m", ondelete="cascade", required=True)
    period_covered     = fields.Char(string="Period Covered")
    withholding_agent  = fields.Char(string="Name of Withholding Agent")
    income_payment     = fields.Monetary(string="Income Payment",       currency_field="currency_id")
    total_tax_withheld = fields.Monetary(string="Total Tax Withheld",   currency_field="currency_id")
    applied_current_mo = fields.Monetary(string="Applied - Current Mo.",currency_field="currency_id")
    currency_id        = fields.Many2one(related="bir_id.currency_id", store=True)


# ============================================================
# MAIN MODEL
# ============================================================

class Bir2550M(models.Model):
    _name        = "bir.2550m"
    _description = "BIR 2550M - Monthly Value-Added Tax Declaration"
    _rec_name    = "display_name"
    _order       = "year desc, month desc, id desc"
    _inherit     = ["mail.thread", "mail.activity.mixin"]

    # ── Identity ──────────────────────────────────────────
    name = fields.Char(string="Reference", readonly=True, copy=False,
                       index=True, default="New")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    company_id  = fields.Many2one("res.company", string="Company", required=True,
                                  default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id",
                                  store=True, readonly=True)

    year  = fields.Integer(string="Year",  required=True,
                           default=lambda self: date.today().year, tracking=True)
    month = fields.Selection(
        selection=[
            ("1","January"),("2","February"),("3","March"),("4","April"),
            ("5","May"),("6","June"),("7","July"),("8","August"),
            ("9","September"),("10","October"),("11","November"),("12","December"),
        ],
        string="Month", required=True,
        default=lambda self: str(date.today().month), tracking=True)

    date_from = fields.Date(compute="_compute_dates", store=True)
    date_to   = fields.Date(compute="_compute_dates", store=True)

    is_amended       = fields.Boolean(string="Amended Return", default=False)
    number_of_sheets = fields.Integer(string="Number of Sheets Attached", default=0)

    # ── Background Info ────────────────────────────────────
    tin                = fields.Char(related="company_id.vat",   readonly=True)
    rdo_code           = fields.Char(string="RDO Code", size=3)
    line_of_business   = fields.Char(string="Line of Business")
    registered_name    = fields.Char(related="company_id.name",  readonly=True)
    telephone_number   = fields.Char(related="company_id.phone", readonly=True)
    zip_code           = fields.Char(related="company_id.zip",   readonly=True)
    registered_address = fields.Text(compute="_compute_registered_address", store=True)
    has_tax_relief     = fields.Boolean(string="Tax Relief under Special Law/Treaty")
    tax_relief_specify = fields.Char(string="Specify Tax Relief")

    # ── State ─────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft","Draft"), ("generated","Generated"),
            ("confirmed","Confirmed"), ("filed","Filed"), ("cancelled","Cancelled"),
        ],
        string="Status", default="draft", required=True, tracking=True, copy=False)

    date_confirmed = fields.Date(readonly=True, copy=False)
    date_filed     = fields.Date(readonly=True, copy=False)
    confirmed_by   = fields.Many2one("res.users", readonly=True, copy=False)
    filed_by       = fields.Many2one("res.users", readonly=True, copy=False)

    # ── Schedule One2many Lines ───────────────────────────
    sch1_ids = fields.One2many("bir.2550m.sch1", "bir_id", string="Schedule 1 - Vatable Sales")
    sch2_ids = fields.One2many("bir.2550m.sch2", "bir_id", string="Schedule 2 - Capital Goods ≤ ₱1M")
    sch3_ids = fields.One2many("bir.2550m.sch3", "bir_id", string="Schedule 3 - Capital Goods > ₱1M")
    sch4_ids = fields.One2many("bir.2550m.sch4", "bir_id", string="Schedule 4 - Sales to Govt Input Tax")
    sch5_ids = fields.One2many("bir.2550m.sch5", "bir_id", string="Schedule 5 - Exempt Sales Input Tax")
    sch6_ids = fields.One2many("bir.2550m.sch6", "bir_id", string="Schedule 6 - Creditable VAT Withheld")
    sch7_ids = fields.One2many("bir.2550m.sch7", "bir_id", string="Schedule 7 - Advance Payments")
    sch8_ids = fields.One2many("bir.2550m.sch8", "bir_id", string="Schedule 8 - VAT on Govt Sales")

    # ── Part II Summary Fields (Items 12–26) ──────────────

    # 12: Vatable Sales - Private (auto-filled from Sch 1, also manually editable)
    item_12a = fields.Monetary(string="12A Vatable Sales - Private",
                               currency_field="currency_id")
    item_12b = fields.Monetary(string="12B Output Tax - Vatable Private",
                               currency_field="currency_id")

    # 13: Sales to Government
    item_13a = fields.Monetary(string="13A Sales to Government", currency_field="currency_id")
    item_13b = fields.Monetary(string="13B Output Tax - Govt (12%)",
                               compute="_compute_output_taxes", store=True,
                               currency_field="currency_id")

    # 14, 15: Zero Rated, Exempt (manual)
    item_14  = fields.Monetary(string="14 Zero Rated Sales/Receipts", currency_field="currency_id")
    item_15  = fields.Monetary(string="15 Exempt Sales/Receipts",     currency_field="currency_id")

    # 16: Totals
    item_16a = fields.Monetary(string="16A Total Sales/Receipts",
                               compute="_compute_totals", store=True, currency_field="currency_id")
    item_16b = fields.Monetary(string="16B Total Output Tax Due",
                               compute="_compute_totals", store=True, currency_field="currency_id")

    # 17: Input Tax Carryover
    item_17a = fields.Monetary(string="17A Input Tax Carried Over from Previous Period",
                               currency_field="currency_id")
    item_17b = fields.Monetary(string="17B Input Tax Deferred on Capital Goods > ₱1M (Prev Period)",
                               currency_field="currency_id")
    item_17c = fields.Monetary(string="17C Transitional Input Tax",  currency_field="currency_id")
    item_17d = fields.Monetary(string="17D Presumptive Input Tax",   currency_field="currency_id")
    item_17e = fields.Monetary(string="17E Others (Carryover)",      currency_field="currency_id")
    item_17f = fields.Monetary(string="17F Total Input Tax Carryover",
                               compute="_compute_input_totals", store=True,
                               currency_field="currency_id")

    # 18: Current Purchases (auto-filled from schedules, also manually editable)
    item_18a = fields.Monetary(string="18A Capital Goods ≤ ₱1M - Purchases (Sch.2)",
                               currency_field="currency_id")
    item_18b = fields.Monetary(string="18B Capital Goods ≤ ₱1M - Input Tax (Sch.2)",
                               currency_field="currency_id")
    item_18c = fields.Monetary(string="18C Capital Goods > ₱1M - Purchases (Sch.3)",
                               currency_field="currency_id")
    item_18d = fields.Monetary(string="18D Capital Goods > ₱1M - Allowable Input Tax (Sch.3)",
                               currency_field="currency_id")
    item_18e = fields.Monetary(string="18E Domestic Purchases of Goods (Non-Capital)",
                               currency_field="currency_id")
    item_18f = fields.Monetary(string="18F Input Tax - Domestic Goods (Non-Capital)",
                               currency_field="currency_id")
    item_18g = fields.Monetary(string="18G Importation of Goods (Non-Capital)",
                               currency_field="currency_id")
    item_18h = fields.Monetary(string="18H Input Tax - Importation",
                               currency_field="currency_id")
    item_18i = fields.Monetary(string="18I Domestic Purchase of Services",
                               currency_field="currency_id")
    item_18j = fields.Monetary(string="18J Input Tax - Domestic Services",
                               currency_field="currency_id")
    item_18k = fields.Monetary(string="18K Services by Non-Residents",
                               currency_field="currency_id")
    item_18l = fields.Monetary(string="18L Input Tax - Non-Resident Services",
                               currency_field="currency_id")
    item_18m = fields.Monetary(string="18M Purchases Not Qualified for Input Tax",
                               currency_field="currency_id")
    item_18n = fields.Monetary(string="18N Others (Purchases)",      currency_field="currency_id")
    item_18o = fields.Monetary(string="18O Input Tax - Others",      currency_field="currency_id")
    item_18p = fields.Monetary(string="18P Total Current Purchases",
                               compute="_compute_input_totals", store=True,
                               currency_field="currency_id")

    # 19: Total Available Input Tax
    item_19  = fields.Monetary(string="19 Total Available Input Tax",
                               compute="_compute_input_totals", store=True,
                               currency_field="currency_id")

    # 20: Deductions from Input Tax (from schedules)
    item_20a = fields.Monetary(string="20A Input Tax on Capital Goods > ₱1M Deferred (Sch.3)",
                               currency_field="currency_id")
    item_20b = fields.Monetary(string="20B Input Tax on Sale to Govt Closed to Expense (Sch.4)",
                               currency_field="currency_id")
    item_20c = fields.Monetary(string="20C Input Tax Allocable to Exempt Sales (Sch.5)",
                               currency_field="currency_id")
    item_20d = fields.Monetary(string="20D VAT Refund/TCC Claimed",  currency_field="currency_id")
    item_20e = fields.Monetary(string="20E Others (Input Tax Deductions)", currency_field="currency_id")
    item_20f = fields.Monetary(string="20F Total Deductions from Input Tax",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")

    # 21, 22
    item_21  = fields.Monetary(string="21 Total Allowable Input Tax (19 less 20F)",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")
    item_22  = fields.Monetary(string="22 Net VAT Payable (16B less 21)",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")

    # 23: Tax Credits (from schedules)
    item_23a = fields.Monetary(string="23A Creditable VAT Withheld (Sch.6)",
                               currency_field="currency_id")
    item_23b = fields.Monetary(string="23B Advance Payments - Sugar/Flour (Sch.7)",
                               currency_field="currency_id")
    item_23c = fields.Monetary(string="23C VAT Withheld on Govt Sales (Sch.8)",
                               currency_field="currency_id")
    item_23d = fields.Monetary(string="23D VAT Paid in Previously Filed Amended Return",
                               currency_field="currency_id")
    item_23e = fields.Monetary(string="23E Advance Payments (BIR Form 0605)",
                               currency_field="currency_id")
    item_23f = fields.Monetary(string="23F Others (Tax Credits)",    currency_field="currency_id")
    item_23g = fields.Monetary(string="23G Total Tax Credits/Payments",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")

    # 24, 25, 26
    item_24  = fields.Monetary(string="24 Tax Still Payable/(Overpayment)",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")
    item_25a = fields.Monetary(string="25A Surcharge",  currency_field="currency_id")
    item_25b = fields.Monetary(string="25B Interest",   currency_field="currency_id")
    item_25c = fields.Monetary(string="25C Compromise", currency_field="currency_id")
    item_25d = fields.Monetary(string="25D Total Penalties",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")
    item_26  = fields.Monetary(string="26 Total Amount Payable/(Overpayment)",
                               compute="_compute_vat_payable", store=True,
                               currency_field="currency_id")

    # ── Payment Details ────────────────────────────────────
    payment_method = fields.Selection(
        selection=[
            ("cash","29 Cash/Bank Debit Memo"), ("check","30 Check"),
            ("tax_debit","31 Tax Debit Memo"),  ("others","32 Others"),
        ], string="Payment Method")
    payment_bank   = fields.Char(string="Drawee Bank/Agency")
    payment_number = fields.Char(string="Payment Number")
    payment_date   = fields.Date(string="Payment Date")
    payment_amount = fields.Monetary(string="Payment Amount", currency_field="currency_id")

    notes = fields.Text(string="Internal Notes")

    # =====================================================
    # COMPUTES
    # =====================================================

    @api.depends("year", "month")
    def _compute_dates(self):
        for rec in self:
            if rec.year and rec.month:
                m = int(rec.month)
                last_day = calendar.monthrange(rec.year, m)[1]
                rec.date_from = date(rec.year, m, 1)
                rec.date_to   = date(rec.year, m, last_day)
            else:
                rec.date_from = rec.date_to = False

    @api.depends("name", "year", "month", "company_id")
    def _compute_display_name(self):
        month_names = {
            "1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun",
            "7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec",
        }
        for rec in self:
            seq = rec.name if rec.name and rec.name != "New" else "Draft"
            mon = month_names.get(rec.month or "1", "")
            rec.display_name = f"2550M | {rec.company_id.name or ''} | {mon} {rec.year} | {seq}"

    @api.depends("company_id")
    def _compute_registered_address(self):
        for rec in self:
            co = rec.company_id
            parts = filter(None, [
                co.street, co.street2, co.city,
                co.state_id.name if co.state_id else "",
                co.country_id.name if co.country_id else "",
            ])
            rec.registered_address = ", ".join(parts)

    def _sync_from_schedules(self):
        """
        Push schedule totals into the Part II summary fields.
        Called explicitly after schedule lines change (not a stored compute)
        so the summary fields remain manually editable on Page 1.
        Accountants can override any value after syncing.
        """
        for rec in self:
            current_sch3 = rec.sch3_ids.filtered(lambda l: not l.is_previous_period)
            rec.write({
                "item_12a": sum(rec.sch1_ids.mapped("sales_amount")),
                "item_12b": sum(rec.sch1_ids.mapped("output_tax")),
                "item_18a": sum(rec.sch2_ids.mapped("amount")),
                "item_18b": sum(rec.sch2_ids.mapped("input_tax")),
                "item_18c": sum(current_sch3.mapped("amount")),
                "item_18d": sum(rec.sch3_ids.mapped("allowable_input_tax")),
                "item_20a": sum(rec.sch3_ids.mapped("balance_input_tax")),
                "item_20b": sum(rec.sch4_ids.mapped("closed_to_expense")),
                "item_20c": sum(rec.sch5_ids.mapped("total_allocable")),
                "item_23a": sum(rec.sch6_ids.mapped("applied_current_mo")),
                "item_23b": sum(rec.sch7_ids.mapped("applied_current_mo")),
                "item_23c": sum(rec.sch8_ids.mapped("applied_current_mo")),
            })

    @api.depends("item_13a")
    def _compute_output_taxes(self):
        for rec in self:
            rec.item_13b = round(rec.item_13a * 0.12, 2)

    @api.depends("item_12a", "item_12b", "item_13a", "item_13b", "item_14", "item_15")
    def _compute_totals(self):
        for rec in self:
            rec.item_16a = rec.item_12a + rec.item_13a + rec.item_14 + rec.item_15
            rec.item_16b = rec.item_12b + rec.item_13b

    @api.depends(
        "item_17a", "item_17b", "item_17c", "item_17d", "item_17e",
        "item_18a", "item_18b", "item_18c", "item_18d",
        "item_18e", "item_18f", "item_18g", "item_18h",
        "item_18i", "item_18j", "item_18k", "item_18l",
        "item_18m", "item_18n", "item_18o",
    )
    def _compute_input_totals(self):
        for rec in self:
            rec.item_17f = (rec.item_17a + rec.item_17b + rec.item_17c
                            + rec.item_17d + rec.item_17e)
            rec.item_18p = (rec.item_18a + rec.item_18c + rec.item_18e
                            + rec.item_18g + rec.item_18i + rec.item_18k
                            + rec.item_18m + rec.item_18n)
            rec.item_19  = (rec.item_17f
                            + rec.item_18b + rec.item_18d + rec.item_18f
                            + rec.item_18h + rec.item_18j + rec.item_18l
                            + rec.item_18o)

    @api.depends(
        "item_19", "item_16b",
        "item_20a", "item_20b", "item_20c", "item_20d", "item_20e",
        "item_23a", "item_23b", "item_23c", "item_23d", "item_23e", "item_23f",
        "item_25a", "item_25b", "item_25c",
    )
    def _compute_vat_payable(self):
        for rec in self:
            rec.item_20f = (rec.item_20a + rec.item_20b + rec.item_20c
                            + rec.item_20d + rec.item_20e)
            rec.item_21  = max(rec.item_19 - rec.item_20f, 0.0)
            rec.item_22  = rec.item_16b - rec.item_21
            rec.item_23g = (rec.item_23a + rec.item_23b + rec.item_23c
                            + rec.item_23d + rec.item_23e + rec.item_23f)
            rec.item_24  = rec.item_22 - rec.item_23g
            rec.item_25d = rec.item_25a + rec.item_25b + rec.item_25c
            rec.item_26  = rec.item_24 + rec.item_25d

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    @api.constrains("year")
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > date.today().year + 1:
                raise ValidationError(
                    f"Year {rec.year} is not valid. "
                    f"Must be between 2000 and {date.today().year + 1}."
                )

    _sql_constraints = [
        (
            "unique_company_year_month",
            "UNIQUE(company_id, year, month)",
            "A BIR 2550M return for this company, year, and month already exists.",
        )
    ]

    # =====================================================
    # WORKFLOW ACTIONS
    # =====================================================

    def _get_month_name(self):
        months = {
            "1":"January","2":"February","3":"March","4":"April",
            "5":"May","6":"June","7":"July","8":"August",
            "9":"September","10":"October","11":"November","12":"December",
        }
        return months.get(self.month or "1", "")

    def action_generate_data(self):
        """
        Auto-generate Sch 1 (Vatable Sales) and Sch 2 (Capital Goods ≤ ₱1M)
        from posted journal entries. Uses credit-only on income accounts and
        debit-only on expense/asset accounts — same pattern as 1601-E.
        """
        for rec in self:
            if rec.state not in ("draft", "generated"):
                raise UserError("Only Draft or Generated returns can pull data. Reset to Draft first.")
            if not rec.date_from or not rec.date_to:
                raise ValidationError("Month/Year not properly set.")

            company_id = rec.company_id.id
            date_from  = rec.date_from
            date_to    = rec.date_to
            AML        = self.env["account.move.line"]

            # ── Vatable Sales → Sch 1 ──
            sales_lines = AML.search([
                ("account_id.account_type", "in", ["income", "income_other"]),
                ("date", ">=", date_from), ("date", "<=", date_to),
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", company_id),
                ("credit", ">", 0),
            ])

            # Clear and recreate Sch 1
            rec.sch1_ids.unlink()
            if sales_lines:
                # Group by account for summary lines
                from collections import defaultdict
                by_account = defaultdict(float)
                for sl in sales_lines:
                    by_account[sl.account_id.name] += (sl.credit - sl.debit)

                sch1_vals = []
                for account_name, amount in by_account.items():
                    if amount > 0:
                        sch1_vals.append({
                            "bir_id": rec.id,
                            "industry": account_name,
                            "atc": "",
                            "sales_amount": round(amount, 2),
                        })
                if sch1_vals:
                    self.env["bir.2550m.sch1"].create(sch1_vals)

            # ── Capital Goods Purchases → Sch 2 ──
            # Find asset accounts with 'equipment', 'furniture', 'machinery', or 'capital'
            capital_accounts = self.env["account.account"].search([
                ("account_type", "in", ["asset_fixed", "asset_non_current"]),
            ])

            rec.sch2_ids.unlink()
            if capital_accounts:
                cap_lines = AML.search([
                    ("account_id", "in", capital_accounts.ids),
                    ("date", ">=", date_from), ("date", "<=", date_to),
                    ("move_id.state", "=", "posted"),
                    ("company_id", "=", company_id),
                    ("debit", ">", 0),
                ])
                sch2_vals = []
                for cl in cap_lines:
                    net_of_vat = round((cl.debit - cl.credit) / 1.12, 2)
                    if net_of_vat > 0 and net_of_vat <= 1_000_000:
                        sch2_vals.append({
                            "bir_id": rec.id,
                            "date_purchased": cl.date,
                            "description": cl.name or cl.move_id.ref or cl.account_id.name,
                            "amount": net_of_vat,
                        })
                if sch2_vals:
                    self.env["bir.2550m.sch2"].create(sch2_vals)

            # Push schedule totals into Part II summary fields
            rec._sync_from_schedules()

            rec.state = "generated"
            rec.message_post(
                body=(
                    f"Data generated for {rec._get_month_name()} {rec.year}. "
                    f"Sch 1: {len(rec.sch1_ids)} line(s). "
                    f"Sch 2: {len(rec.sch2_ids)} line(s). "
                    "Part II summary fields updated from schedules. "
                    "Please review and fill in Schedules 3–8 manually."
                )
            )

    def action_sync_from_schedules(self):
        """
        Manually push all schedule totals into Part II summary fields.
        Use this after editing schedules to update the summary without
        re-generating all data from journal entries.
        """
        for rec in self:
            if rec.state in ("confirmed", "filed", "cancelled"):
                raise UserError("Cannot sync a Confirmed, Filed, or Cancelled return.")
        self._sync_from_schedules()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Schedules Synced",
                "message": "Part II summary fields have been updated from schedule totals.",
                "type": "success",
                "sticky": False,
            }
        }

    def action_sync_from_schedules(self):
        """
        Manually push all schedule totals into Part II summary fields.
        Use after editing schedules to update the summary without
        re-generating from journal entries.
        """
        for rec in self:
            if rec.state in ("confirmed", "filed", "cancelled"):
                raise UserError("Cannot sync a Confirmed, Filed, or Cancelled return.")
        self._sync_from_schedules()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Schedules Synced",
                "message": "Part II summary fields updated from schedule totals.",
                "type": "success",
                "sticky": False,
            }
        }

    def action_confirm(self):
        for rec in self:
            if rec.state != "generated":
                raise UserError("Only a Generated return can be confirmed.")
            if rec.name == "New":
                rec.name = (
                    self.env["ir.sequence"].next_by_code("bir.2550m") or "New"
                )
            rec.state        = "confirmed"
            rec.date_confirmed = date.today()
            rec.confirmed_by   = self.env.user
            rec.message_post(body=f"Return confirmed by {self.env.user.name}. Reference: {rec.name}")

    def action_file(self):
        for rec in self:
            if rec.state != "confirmed":
                raise UserError("Only a Confirmed return can be filed.")
            rec.state      = "filed"
            rec.date_filed = date.today()
            rec.filed_by   = self.env.user
            rec.message_post(body=f"Return [{rec.name}] filed with BIR by {self.env.user.name}.")

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == "filed":
                raise UserError("A Filed return cannot be reset. Create an amended return.")
            if rec.state == "cancelled":
                raise UserError("A Cancelled return cannot be reset to Draft.")
            rec.state          = "draft"
            rec.date_confirmed = False
            rec.date_filed     = False
            rec.confirmed_by   = False
            rec.filed_by       = False
            rec.message_post(body=f"Return [{rec.name}] reset to Draft.")

    def action_cancel(self):
        for rec in self:
            if rec.state in ("confirmed", "filed"):
                raise UserError("Cannot cancel a Confirmed or Filed return.")
            rec.state = "cancelled"
            rec.message_post(body=f"Return [{rec.name}] cancelled.")

    def action_create_monthly_returns(self):
        """Batch-create all 12 months for this return's year. Skips existing."""
        self.ensure_one()
        target_year    = self.year
        target_company = self.company_id.id
        created = []
        skipped = []
        month_names = {
            "1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun",
            "7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec",
        }
        for m in range(1, 13):
            m_str = str(m)
            existing = self.search([
                ("company_id", "=", target_company),
                ("year", "=", target_year),
                ("month", "=", m_str),
            ], limit=1)
            if existing:
                skipped.append(month_names[m_str])
                continue
            self.create({
                "company_id": target_company,
                "year": target_year,
                "month": m_str,
                "state": "draft",
            })
            created.append(month_names[m_str])

        msg = f"Created: {', '.join(created) or 'none'}. Skipped existing: {', '.join(skipped) or 'none'}."
        self.message_post(body=msg)

        return {
            "type": "ir.actions.act_window",
            "name": f"BIR 2550M — {target_year}",
            "res_model": "bir.2550m",
            "view_mode": "list,form",
            "domain": [("company_id", "=", target_company), ("year", "=", target_year)],
        }
