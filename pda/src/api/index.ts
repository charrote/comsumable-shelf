const BASE_URL = 'http://localhost:8080/api'

function getHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export async function loginApi(username: string, password: string) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  return res.json()
}

export async function scanInboundApi(barcode: string, operator: string) {
  const res = await fetch(`${BASE_URL}/receipts/scan`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ barcode, operator }),
  })
  return res.json()
}

export async function calculateIssueApi(orderId: number, strategy: string = 'tail_first') {
  const res = await fetch(`${BASE_URL}/issues/${orderId}/calculate`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ strategy }),
  })
  return res.json()
}

export async function confirmPickApi(orderId: number, barcode: string, palletId: number) {
  const res = await fetch(`${BASE_URL}/issues/${orderId}/confirm-pick`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ barcode, pallet_id: palletId }),
  })
  return res.json()
}

export async function getInventoryApi() {
  const res = await fetch(`${BASE_URL}/inventory/tracking`, {
    method: 'GET',
    headers: getHeaders(),
  })
  return res.json()
}
