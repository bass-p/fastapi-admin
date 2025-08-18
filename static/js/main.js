// main.js
//
// Fetch products from the backend and render them on the homepage. Manage
// cart interactions by storing cart contents in localStorage. A simple
// cart badge displays the number of items currently in the cart.

document.addEventListener('DOMContentLoaded', () => {
  loadProducts();
  updateCartCount();
});

function loadProducts() {
  fetch('/api/products')
    .then(res => res.json())
    .then(data => {
      // The API returns an object with a `products` array
      const products = data.products || [];
      const list = document.getElementById('product-list');
      list.innerHTML = '';
      products.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
          <img src="${product.image_url}" alt="${product.name}">
          <h3>${product.name}</h3>
          <p>${product.description}</p>
          <div class="price">NRP ${product.price.toFixed(2)}</div>
          <button class="btn btn-primary">Add to Cart</button>
        `;
        const btn = card.querySelector('button');
        btn.addEventListener('click', () => {
          addToCart(product.id);
        });
        list.appendChild(card);
      });
    })
    .catch(err => {
      console.error('Error loading products', err);
    });
}

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
  Object.values(cart).forEach(qty => {
    count += qty;
  });
  const badge = document.getElementById('cart-count');
  if (badge) badge.textContent = count;
}

function addToCart(productId) {
  const cart = getCart();
  if (cart[productId]) {
    cart[productId] += 1;
  } else {
    cart[productId] = 1;
  }
  saveCart(cart);
  updateCartCount();
  alert('Added to cart!');
}