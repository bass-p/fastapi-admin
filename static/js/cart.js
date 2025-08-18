// cart.js
//
// Render the contents of the shopping cart stored in localStorage. Allow
// users to adjust quantities or remove items. Display the running
// subtotal and allow navigation to checkout when the cart is not empty.

document.addEventListener('DOMContentLoaded', () => {
  updateCartCount();
  renderCart();
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

function renderCart() {
  const cart = getCart();
  const keys = Object.keys(cart);
  const emptyMsg = document.getElementById('empty-message');
  const table = document.getElementById('cart-table');
  const tbody = table.querySelector('tbody');
  const totalDiv = document.getElementById('cart-total');
  const checkoutBtn = document.getElementById('checkout-btn');
  if (keys.length === 0) {
    emptyMsg.style.display = '';
    table.style.display = 'none';
    totalDiv.textContent = '';
    checkoutBtn.style.pointerEvents = 'none';
    checkoutBtn.style.opacity = '0.5';
    return;
  }
  // Fetch product data to resolve names and prices
  fetch('/api/products')
    .then(res => res.json())
    .then(data => {
      // The API returns an object with a `products` array
      const products = data.products || [];
      // Map products by id for quick lookup
      const productMap = {};
      products.forEach(p => { productMap[p.id] = p; });
      tbody.innerHTML = '';
      let total = 0;
      keys.forEach(pid => {
        const quantity = cart[pid];
        const product = productMap[pid];
        if (!product) return;
        const subtotal = product.price * quantity;
        total += subtotal;
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${product.name}</td>
          <td><input type="number" min="1" value="${quantity}" data-pid="${pid}" style="width:60px;"></td>
          <td>NRP ${product.price.toFixed(2)}</td>
          <td>NRP ${subtotal.toFixed(2)}</td>
          <td><button class="btn btn-secondary" data-remove="${pid}">Remove</button></td>
        `;
        tbody.appendChild(tr);
      });
      totalDiv.textContent = `Total: NRP ${total.toFixed(2)}`;
      table.style.display = '';
      emptyMsg.style.display = 'none';
      checkoutBtn.style.pointerEvents = '';
      checkoutBtn.style.opacity = '';
      // Attach event listeners after rows are created
      tbody.querySelectorAll('input[type="number"]').forEach(input => {
        input.addEventListener('change', e => {
          const pid = input.getAttribute('data-pid');
          let qty = parseInt(input.value, 10);
          if (isNaN(qty) || qty < 1) qty = 1;
          input.value = qty;
          const currentCart = getCart();
          currentCart[pid] = qty;
          saveCart(currentCart);
          updateCartCount();
          // Re-render to update subtotals and total
          renderCart();
        });
      });
      tbody.querySelectorAll('button[data-remove]').forEach(btn => {
        btn.addEventListener('click', e => {
          const pid = btn.getAttribute('data-remove');
          const currentCart = getCart();
          delete currentCart[pid];
          saveCart(currentCart);
          updateCartCount();
          renderCart();
        });
      });
    })
    .catch(err => {
      console.error('Error loading cart products', err);
    });
}