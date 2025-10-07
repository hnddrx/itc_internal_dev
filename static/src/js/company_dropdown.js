document.addEventListener('DOMContentLoaded', function () {
    function waitForElement(selector, callback, timeout = 5000) {
        const start = Date.now();
        function check() {
            const el = document.querySelector(selector);
            if (el) return callback(el);
            if (Date.now() - start > timeout) return;
            setTimeout(check, 100);
        }
        check();
    }

    function simulateClick(el) {
        ['mousedown', 'mouseup', 'click'].forEach(evtType => {
            const evt = new MouseEvent(evtType, { bubbles: true, cancelable: true, view: window });
            el.dispatchEvent(evt);
        });
    }

    function closeOpenDropdowns(excludeSelector) {
        const openDropdowns = document.querySelectorAll('button.o-dropdown.dropdown-toggle.dropdown[aria-expanded="true"]');
        openDropdowns.forEach(btn => {
            if (!btn.matches(excludeSelector)) {
                simulateClick(btn);
            }
        });
    }

    function activateAllCompanies(companyDropdownBtn) {
        const items = document.querySelectorAll('.o_switch_company_item');
        const targetCompanyId = '32';
        let targetLogIntoButton = null;

        // Check all checkboxes
        items.forEach(item => {
            const checkboxIcon = item.querySelector('[role="menuitemcheckbox"] i');
            const companyId = item.getAttribute('data-company-id');
            if (checkboxIcon && checkboxIcon.classList.contains('fa-square-o')) {
                simulateClick(checkboxIcon);
            }
            if (companyId === targetCompanyId) {
                targetLogIntoButton = item.querySelector('.log_into');
            }
        });

        // Select company 32
        setTimeout(() => {
            if (targetLogIntoButton && !targetLogIntoButton.classList.contains('bg-primary-subtle')) {
                simulateClick(targetLogIntoButton);
            }
        }, 300);

        // Confirm selection
        setTimeout(() => {
            const confirmBtn = document.querySelector('.o_switch_company_menu_buttons .btn.btn-primary');
            if (confirmBtn) simulateClick(confirmBtn);
        }, 600);

        // Close dropdown
        setTimeout(() => {
            if (companyDropdownBtn.getAttribute('aria-expanded') === 'true') {
                simulateClick(companyDropdownBtn);
            }
            closeOpenDropdowns('.o_switch_company_menu button');
        }, 900);
    }

    // ✅ Add search input and select all button
    function injectSearchAndSelectAll() {
        const dropdown = document.querySelector('.o_switch_company_menu_dropdown');
        if (!dropdown || dropdown.querySelector('.custom-tools')) return;

        const toolsWrapper = document.createElement('div');
        toolsWrapper.className = 'custom-tools';
        toolsWrapper.style.padding = '8px';

        // Search bar
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search companies...';
        searchInput.style.width = '100%';
        searchInput.style.marginBottom = '6px';
        searchInput.style.padding = '4px';

        searchInput.addEventListener('input', function () {
            const filter = searchInput.value.toLowerCase();
            const items = dropdown.querySelectorAll('.o_switch_company_item');
            items.forEach(item => {
                const name = item.textContent.toLowerCase();
                item.style.display = name.includes(filter) ? '' : 'none';
            });
        });

        // Select All button
        const selectAllBtn = document.createElement('button');
        selectAllBtn.textContent = 'Select All';
        selectAllBtn.style.width = '100%';
        selectAllBtn.style.padding = '6px';
        selectAllBtn.style.cursor = 'pointer';

        selectAllBtn.addEventListener('click', () => {
            const items = dropdown.querySelectorAll('.o_switch_company_item');
            items.forEach(item => {
                const checkboxIcon = item.querySelector('[role="menuitemcheckbox"] i');
                if (checkboxIcon && checkboxIcon.classList.contains('fa-square-o')) {
                    simulateClick(checkboxIcon);
                }
            });
        });

        toolsWrapper.appendChild(searchInput);
        toolsWrapper.appendChild(selectAllBtn);

        // Insert tools at top of dropdown
        dropdown.prepend(toolsWrapper);
    }

    // Entry point
    waitForElement('.o_switch_company_menu button', (companyDropdownBtn) => {
        closeOpenDropdowns('.o_switch_company_menu button');
        simulateClick(companyDropdownBtn);

        waitForElement('.o_switch_company_menu_dropdown', () => {
            injectSearchAndSelectAll();         // Inject custom UI
            activateAllCompanies(companyDropdownBtn);  // Optionally activate company 32
        });
    });

    // Optional: hide dropdown permanently (commented out)
    // function hideCompanyDropdown() {
    //     const dropdown = document.querySelector('.o_switch_company_menu');
    //     if (dropdown) {
    //         dropdown.style.pointerEvents = 'none';
    //         dropdown.style.opacity = '0';
    //         dropdown.style.position = 'absolute';
    //         dropdown.style.right = '9999px';
    //     }
    // }
    // waitForElement('.o_switch_company_menu', hideCompanyDropdown);
});
