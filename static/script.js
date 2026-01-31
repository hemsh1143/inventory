// Add item row in purchase/sales forms
function addItemRow(containerId) {
    const container = document.getElementById(containerId);
    const row = document.createElement('div');
    row.className = 'row mb-2 item-row';
    row.innerHTML = `
        <div class="col-md-4">
            <select name="item_id[]" class="form-select item-select" required>
                <option value="">Select Item</option>
                {% for item in items %}
                <option value="{{ item.id }}" data-price="{{ item.selling_price }}">{{ item.name }} - Stock: {{ item.current_stock }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="col-md-2">
            <input type="number" name="quantity[]" class="form-control quantity" placeholder="Qty" step="0.01" required>
        </div>
        <div class="col-md-2">
            <input type="number" name="unit_cost[]" class="form-control unit-cost" placeholder="Unit Cost" step="0.01" required>
        </div>
        <div class="col-md-2">
            <input type="text" class="form-control total" placeholder="Total" readonly>
        </div>
        <div class="col-md-2">
            <button type="button" class="btn btn-danger btn-sm" onclick="removeItemRow(this)">Remove</button>
        </div>
    `;
    container.appendChild(row);
}

// Remove item row
function removeItemRow(button) {
    button.closest('.item-row').remove();
    calculateTotal();
}

// Calculate total for purchase/sales
function calculateTotal() {
    let total = 0;
    document.querySelectorAll('.item-row').forEach(row => {
        const quantity = parseFloat(row.querySelector('.quantity').value) || 0;
        const unitCost = parseFloat(row.querySelector('.unit-cost').value) || 0;
        const totalInput = row.querySelector('.total');
        const rowTotal = quantity * unitCost;
        
        totalInput.value = rowTotal.toFixed(2);
        total += rowTotal;
    });
    
    document.getElementById('totalAmount').textContent = total.toFixed(2);
}

// Auto-fill unit price when item is selected
document.addEventListener('change', function(e) {
    if (e.target.classList.contains('item-select')) {
        const selectedOption = e.target.options[e.target.selectedIndex];
        const unitPrice = selectedOption.getAttribute('data-price');
        const row = e.target.closest('.item-row');
        
        if (unitPrice && row.querySelector('.unit-cost')) {
            row.querySelector('.unit-cost').value = unitPrice;
            calculateTotal();
        }
    }
});

// Calculate on input change
document.addEventListener('input', function(e) {
    if (e.target.classList.contains('quantity') || e.target.classList.contains('unit-cost')) {
        calculateTotal();
    }
});