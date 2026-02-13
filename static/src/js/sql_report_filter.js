/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { HtmlField } from "@web/views/fields/html/html_field";

function addColumnFilters(table) {
    const thead = table.querySelector("thead");
    if (!thead) return;

    // Prevent adding the filter row multiple times
    if (thead.querySelector(".filter-row")) return;

    const filterRow = document.createElement("tr");
    filterRow.classList.add("filter-row");

    Array.from(thead.rows[0].cells).forEach(() => {
        const th = document.createElement("th");
        const input = document.createElement("input");
        input.type = "text";
        input.placeholder = "Filter";
        input.style.width = "95%";
        input.style.boxSizing = "border-box";

        input.addEventListener("input", (event) => {
            const filterValue = event.target.value.toLowerCase();
            const tbody = table.querySelector("tbody");
            Array.from(tbody.rows).forEach((row) => {
                const cell = row.cells[th.cellIndex];
                if (!cell) return;
                const cellText = cell.textContent.toLowerCase();
                row.style.display = cellText.includes(filterValue) ? "" : "none";
            });
        });

        th.appendChild(input);
        filterRow.appendChild(th);
    });

    thead.appendChild(filterRow);
}

patch(HtmlField.prototype, {
    mounted() {
        this._super(...arguments);

        // Watch for table inside o_sql_report_result
        const container = this.el.querySelector(".o_sql_report_result");
        if (!container) return;

        const observer = new MutationObserver(() => {
            const tables = container.querySelectorAll("table");
            tables.forEach(addColumnFilters);
        });

        observer.observe(container, { childList: true, subtree: true });
    }
}, "itc_internal_dev.sql_report_filter");
