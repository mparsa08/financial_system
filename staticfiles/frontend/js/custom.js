// Custom JS for Financial System

document.addEventListener('DOMContentLoaded', function() {
    var toggleBtn = document.getElementById('toggle-optional');
    var optionalSection = document.getElementById('optional-fields');

    if (toggleBtn && optionalSection) {
        toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (optionalSection.style.display === 'none' || optionalSection.style.display === '') {
                optionalSection.style.display = 'block';
                toggleBtn.textContent = toggleBtn.getAttribute('data-hide-text');
            } else {
                optionalSection.style.display = 'none';
                toggleBtn.textContent = toggleBtn.getAttribute('data-show-text');
            }
        });
    }

    var form = document.getElementById('direct-trade-form');
    if (form) {
        form.addEventListener('submit', function() {
            var grossField = document.getElementById('id_gross_profit_or_loss');
            var gross = parseFloat(grossField ? grossField.value : 0);
            ['broker', 'trader'].forEach(function(type) {
                var checkbox = document.getElementById(type + '_commission_percent');
                var field = document.getElementById('id_' + type + '_commission');
                if (checkbox && checkbox.checked && field && !isNaN(gross)) {
                    var percentVal = parseFloat(field.value);
                    if (!isNaN(percentVal)) {
                        field.value = (gross * percentVal / 100).toFixed(2);
                    }
                }
            });
        });
    }
});
