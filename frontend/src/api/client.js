/**
 * API Client — Fetch wrapper with JWT auth interceptor
 */

const API_BASE = '/api';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function getToken() {
  return localStorage.getItem('setprice_token');
}

function setToken(token) {
  localStorage.setItem('setprice_token', token);
}

function removeToken() {
  localStorage.removeItem('setprice_token');
}

async function request(endpoint, { method = 'GET', body = null, auth = true } = {}) {
  const headers = {};

  if (body && !(body instanceof URLSearchParams)) {
    headers['Content-Type'] = 'application/json';
  }

  if (auth) {
    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const config = { method, headers };

  if (body) {
    config.body = body instanceof URLSearchParams ? body : JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}/${endpoint}`, config);

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    if (res.status === 401) {
      removeToken();
      window.location.reload();
    }
    throw new ApiError(errData.detail || 'API hatası oluştu', res.status, errData);
  }

  if (res.status === 204) return null;
  return res.json();
}

// --- Auth ---
export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const data = await request('auth/login', {
    method: 'POST',
    body: formData,
    auth: false,
  });
  setToken(data.access_token);
  return data;
}

export async function register(email, password) {
  return request('auth/register', {
    method: 'POST',
    body: { email, password },
    auth: false,
  });
}

export async function getMe() {
  return request('auth/me');
}

// --- Sets ---
export async function getSets() {
  return request('sets');
}

export async function getSetById(setId) {
  return request(`sets/${setId}`);
}

export async function createSet(name, targetBudget = 0) {
  return request('sets', {
    method: 'POST',
    body: { name, target_budget: targetBudget },
  });
}

export async function updateSet(setId, data) {
  return request(`sets/${setId}`, {
    method: 'PUT',
    body: data,
  });
}

export async function deleteSet(setId) {
  return request(`sets/${setId}`, { method: 'DELETE' });
}

// --- Products ---
export async function addProductToSet(setId, { originalLink, libraryProductId }) {
  const body = {};
  if (libraryProductId) body.library_product_id = libraryProductId;
  else if (originalLink) body.original_link = originalLink;

  return request(`sets/${setId}/products`, {
    method: 'POST',
    body,
  });
}

export async function updateProduct(productId, data) {
  return request(`products/${productId}`, {
    method: 'PUT',
    body: data,
  });
}

export async function deleteProduct(productId) {
  return request(`products/${productId}`, { method: 'DELETE' });
}

// --- Library ---
export async function getLibraryProducts(category) {
  const query = category ? `?category=${encodeURIComponent(category)}` : '';
  return request(`library/products${query}`);
}

export async function getLibraryCategories() {
  return request('library/categories');
}

export async function scanLibraryProduct(id) {
  return request(`library/products/${id}/scan`, { method: 'POST' });
}

export async function scanAllLibraryProducts() {
  return request('library/products/scan-all', { method: 'POST' });
}

export async function deleteLibraryProduct(id) {
  return request(`library/products/${id}`, { method: 'DELETE' });
}

export async function addLibraryProduct(originalLink) {
  return request('library/products', {
    method: 'POST',
    body: { original_link: originalLink }
  });
}

// --- Scan ---
export async function scanSet(setId) {
  return request(`sets/${setId}/scan`, { method: 'POST' });
}

// --- History & Alternatives ---
export async function getProductHistory(productId) {
  return request(`products/${productId}/history`);
}

export async function getProductAlternatives(productId) {
  return request(`products/${productId}/compare`);
}

// Token utilities for external use
export { getToken, setToken, removeToken };
