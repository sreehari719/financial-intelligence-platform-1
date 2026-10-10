const API_URL =
  import.meta.env.VITE_API_URL ||
  "https://backend-tau-nine-54.vercel.app";
export async function fetchDashboard() {
  const token = localStorage.getItem("access_token");

  const response = await fetch(`${API_URL}/api/dashboard`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...(token
        ? { Authorization: `Bearer ${token}` }
        : {}),
    },
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error("Authentication failed. Please log in.");
    }

    throw new Error(`Dashboard request failed: ${response.status}`);
  }

  return await response.json();
}

export function formatCurrency(value) {
  const amount = Number(value);

  if (value === null || value === undefined || !Number.isFinite(amount)) {
    return "--";
  }

  return amount.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });
}

export function getDashboardValue(data, ...keys) {
  for (const key of keys) {
    if (data?.[key] !== undefined && data[key] !== null) {
      return data[key];
    }
  }

  return null;
}
