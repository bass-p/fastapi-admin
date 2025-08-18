// checkout.js for eSewa integration
//
// Build an order summary from the items stored in localStorage and
// submit the order to the backend. After the order is created the
// script requests payment form fields from the server and posts the
// customer to the eSewa gateway. On completion eSewa will redirect
// back to the application via the configured success/failure URLs.

document.addEventListener('DOMContentLoaded', () => {
  updateCartCount();
  prepareCheckout();
});

function getCart() {
  try {
    return JSON.parse(localStorage.getItem('cart') || '{}');
  } catch (e) {
    return {};
  }
}

function saveCart(cart) {
  localStorage.setItem('cart', JSON.stringify(cart));
}

function updateCartCount() {
  const cart = getCart();
  let count = 0;
  Object.values(cart).forEach(qty => { count += qty; });
  const badge = document.getElementById('cart-count');
  if (badge) badge.textContent = count;
}

function prepareCheckout() {
  const cart = getCart();
  const keys = Object.keys(cart);
  const summaryDiv = document.getElementById('summary');
  const form = document.getElementById('checkout-form');
  if (keys.length === 0) {
    summaryDiv.innerHTML = '<p>Your cart is empty. <a href="/">Go back to shop</a>.</p>';
    form.style.display = 'none';
    return;
  }
  // Fetch product data to display summary
  fetch('/api/products')
    .then(res => res.json())
    .then(data => {
      const products = data.products || [];
      const productMap = {};
      products.forEach(p => { productMap[p.id] = p; });
      let amount = 0;
      let summaryHtml = '<table class="cart-table"><thead><tr><th>Product</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead><tbody>';
      keys.forEach(pid => {
        const qty = cart[pid];
        const product = productMap[pid];
        if (!product) return;
        const subtotal = product.price * qty;
        amount += subtotal;
        summaryHtml += `<tr><td>${product.name}</td><td>${qty}</td><td>NRP ${product.price.toFixed(2)}</td><td>NRP ${subtotal.toFixed(2)}</td></tr>`;
      });
      summaryHtml += '</tbody></table>';
      // Compute charges: VAT 13%, no service or delivery charges
      const taxAmount = amount * 0.13;
      const serviceCharge = 0;
      const deliveryCharge = 0;
      const totalAmount = amount + taxAmount + serviceCharge + deliveryCharge;
      summaryHtml += `<p style="margin-top:1rem;"><strong>Subtotal:</strong> NRP ${amount.toFixed(2)}</p>`;
      summaryHtml += `<p><strong>VAT (13%):</strong> NRP ${taxAmount.toFixed(2)}</p>`;
      summaryHtml += `<p><strong>Total:</strong> NRP ${totalAmount.toFixed(2)}</p>`;
      summaryDiv.innerHTML = summaryHtml;
      // Handle form submission
      form.addEventListener('submit', e => {
        e.preventDefault();
        const payload = {
          customerName: document.getElementById('name').value.trim(),
          customerEmail: document.getElementById('email').value.trim(),
          customerPhone: document.getElementById('phone').value.trim(),
          customerAddress: document.getElementById('address').value.trim(),
          cart: keys.map(pid => ({ productId: parseInt(pid), quantity: cart[pid] })),
          tax_amount: parseFloat(taxAmount.toFixed(2)),
          service_charge: parseFloat(serviceCharge.toFixed(2)),
          delivery_charge: parseFloat(deliveryCharge.toFixed(2))
        };
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        // Create order
        fetch('/api/order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
          .then(res => res.json())
          .then(order => {
            if (order.error) throw new Error(order.error);
            // Request payment initiation
            return fetch('/api/initiate-payment', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ orderId: order.orderId })
            });
          })
          .then(res => res.json())
          .then(data => {
            if (data.error) throw new Error(data.error);
            const { gatewayUrl, formData } = data;
            // Build and submit form to eSewa
            const paymentForm = document.createElement('form');
            paymentForm.action = gatewayUrl;
            paymentForm.method = 'POST';
            Object.keys(formData).forEach(key => {
              const input = document.createElement('input');
              input.type = 'hidden';
              input.name = key;
              input.value = formData[key];
              paymentForm.appendChild(input);
            });
            document.body.appendChild(paymentForm);
            localStorage.removeItem('cart');
            paymentForm.submit();
          })
          .catch(err => {
            alert('Error processing order: ' + err.message);
            submitBtn.disabled = false;
          });
      });
    })
    .catch(err => {
      summaryDiv.innerHTML = '<p>Failed to load your cart. Please try again later.</p>';
      console.error(err);
      form.style.display = 'none';
    });
}