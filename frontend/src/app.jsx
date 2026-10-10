import React, { useEffect, useState } from "react";
import "./style.css";

const API = (
  import.meta.env.VITE_API_URL ||
  "https://backend-tau-nine-54.vercel.app"
).replace(/\/$/, "");

const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));

function readToken() {
  return sessionStorage.getItem("finsight_token") || "";
}

async function api(path, options = {}) {
  const token = readToken();

  const headers = {
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers,
  });

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      result.detail || result.message || `Request failed (${response.status})`
    );
  }

  return result;
}

function Card({ title, value, detail }) {
  return (
    <div className="card metric">
      <span className="muted">{title}</span>
      <h2>{value}</h2>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [identifier, setIdentifier] = useState("");
  const [mpin, setMpin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");

    if (!/^\d{6}$/.test(mpin)) {
      setError("MPIN must contain exactly six digits.");
      return;
    }

    setBusy(true);

    try {
      const result = await api(`/api/auth/${mode === "login" ? "login" : "register"}`, {
        method: "POST",
        body: JSON.stringify({ identifier, mpin }),
      });

      if (mode === "register") {
        setMode("login");
        setMpin("");
        setError("Registration successful. Please log in.");
      } else {
        sessionStorage.setItem("finsight_token", result.access_token);
        onLogin();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-wrap">
      <section className="auth-card card">
        <div className="brand-mark">F</div>
        <p className="eyebrow">PERSONAL FINANCIAL INTELLIGENCE</p>
        <h1>FinSight</h1>
        <p className="muted">
          Understand your money. Monitor risk. Build better savings habits.
        </p>

        <div className="tabs">
          <button
            className={mode === "login" ? "tab active" : "tab"}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Login
          </button>
          <button
            className={mode === "register" ? "tab active" : "tab"}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={submit} className="form">
          <label>Email or phone number</label>
          <input
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="you@example.com or phone number"
            required
          />

          <label>Six-digit MPIN</label>
          <input
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            type="password"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            minLength={6}
            value={mpin}
            onChange={(e) =>
              setMpin(e.target.value.replace(/\D/g, "").slice(0, 6))
            }
            placeholder="••••••"
            required
          />

          {error && <div className="notice">{error}</div>}

          <button className="primary full" disabled={busy}>
            {busy
              ? "Please wait..."
              : mode === "login"
              ? "Log in securely"
              : "Create account"}
          </button>
        </form>

        <p className="muted tiny">
          Use a unique MPIN. Do not reuse your bank, card or UPI PIN.
        </p>
      </section>
    </main>
  );
}

function Dashboard({ dashboard, transactions }) {
  const flagged = transactions.filter(
    (t) => ["SUSPICIOUS", "HIGH RISK"].includes(t.decision)
  );

  const income = transactions
    .filter((t) => String(t.category).toLowerCase() === "income")
    .reduce((sum, t) => sum + Number(t.amount), 0);

  const expenses = transactions
    .filter((t) => String(t.category).toLowerCase() !== "income")
    .reduce((sum, t) => sum + Number(t.amount), 0);

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h1>Your financial dashboard</h1>
          <p className="muted">Your recorded transactions and portfolio at a glance.</p>
        </div>
      </div>

      <div className="metrics-grid">
        <Card title="Recorded transaction value" value={money(dashboard.transaction_value)} />
        <Card title="Transactions" value={dashboard.transaction_count || 0} />
        <Card title="Portfolio value" value={money(dashboard.portfolio_value)} />
        <Card title="Transactions flagged" value={dashboard.suspicious_transactions || 0} />
        <Card title="Income category total" value={money(income)} />
        <Card title="Other recorded transactions" value={money(expenses)} />
      </div>

      {flagged.length > 0 && (
        <div className="alert-banner">
          <strong>Security attention required</strong>
          <p>
            {flagged.length} transaction(s) were flagged for review.
            Check Fraud Intelligence and verify them with your bank if needed.
          </p>
        </div>
      )}

      <section className="card">
        <h2>Recent transactions</h2>
        <TransactionTable rows={(dashboard.recent_transactions || [])} />
      </section>

      <p className="muted tiny">
        FinSight calculates totals from records available in this account.
        They are not a live bank balance.
      </p>
    </>
  );
}

function TransactionTable({ rows }) {
  if (!rows.length) {
    return <p className="muted">No transactions recorded yet.</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Location</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td>
                {t.transaction_time
                  ? new Date(t.transaction_time).toLocaleString()
                  : "—"}
              </td>
              <td>{t.category}</td>
              <td>{t.location}</td>
              <td>{money(t.amount)}</td>
              <td>
                <span className={`status ${String(t.decision || "LEGITIMATE").toLowerCase().replace(/\s+/g, "-")}`}>
                  {t.decision || "LEGITIMATE"}
                </span>
              </td>
              <td>{Number(t.risk_score || 0).toFixed(0)}/100</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Transactions({ transactions, refresh, notify }) {
  const [form, setForm] = useState({
    amount: "",
    category: "",
    location: "",
    device: "Manual entry",
    transaction_time: "",
  });
  const [csvFile, setCsvFile] = useState(null);
  const [busy, setBusy] = useState(false);

  function change(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function addTransaction(e) {
    e.preventDefault();
    setBusy(true);

    try {
      const payload = {
        ...form,
        amount: Number(form.amount),
        transaction_time: form.transaction_time
          ? new Date(form.transaction_time).toISOString()
          : null,
      };

      const result = await api("/api/transactions", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      notify(
        `Transaction saved. Risk: ${result.decision}. ${(
          result.risk_factors || []
        ).join("; ")}`
      );

      setForm({
        amount: "",
        category: "",
        location: "",
        device: "Manual entry",
        transaction_time: "",
      });

      await refresh();
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function importCSV(e) {
    e.preventDefault();

    if (!csvFile) {
      notify("Choose a CSV file first.");
      return;
    }

    const body = new FormData();
    body.append("file", csvFile);
    setBusy(true);

    try {
      const result = await api("/api/transactions/import-csv", {
        method: "POST",
        body,
      });

      notify(result.message);
      setCsvFile(null);
      e.target.reset();
      await refresh();
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR RECORDS</p>
          <h1>Transactions</h1>
          <p className="muted">Add records or import a bank-exported CSV.</p>
        </div>
      </div>

      <section className="card">
        <h2>Add a transaction</h2>
        <form className="form grid-form" onSubmit={addTransaction}>
          <label>
            Amount (₹)
            <input
              name="amount"
              type="number"
              min="0.01"
              step="0.01"
              value={form.amount}
              onChange={change}
              required
            />
          </label>

          <label>
            Category / description
            <input
              name="category"
              value={form.category}
              onChange={change}
              placeholder="Groceries, salary, rent..."
              required
            />
          </label>

          <label>
            Location / merchant
            <input
              name="location"
              value={form.location}
              onChange={change}
              placeholder="Merchant or location"
              required
            />
          </label>

          <label>
            Payment method / device
            <input
              name="device"
              value={form.device}
              onChange={change}
              placeholder="UPI, card, cash..."
              required
            />
          </label>

          <label>
            Date and time (optional)
            <input
              name="transaction_time"
              type="datetime-local"
              value={form.transaction_time}
              onChange={change}
            />
          </label>

          <button className="primary" disabled={busy}>
            Save and screen transaction
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Import CSV</h2>
        <p className="muted">
          Required columns: <code>amount</code> and{" "}
          <code>category</code> or <code>description</code>. Optional columns
          include <code>date</code>, <code>location</code> and{" "}
          <code>device</code>. Maximum file size: 2 MB.
        </p>

        <form className="upload-row" onSubmit={importCSV}>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
          />
          <button className="secondary" disabled={busy}>
            Import CSV
          </button>
        </form>
      </section>

      <section className="card">
        <h2>All transactions</h2>
        <TransactionTable rows={transactions} />
      </section>
    </>
  );
}

function Portfolio({ notify, refreshKey }) {
  const [portfolio, setPortfolio] = useState(null);
  const [form, setForm] = useState({
    asset: "",
    asset_type: "Savings",
    invested_value: "",
    current_value: "",
  });

  async function load() {
    try {
      setPortfolio(await api("/api/portfolio"));
    } catch (err) {
      notify(err.message);
    }
  }

  useEffect(() => {
    load();
  }, [refreshKey]);

  async function submit(e) {
    e.preventDefault();

    try {
      await api("/api/portfolio/assets", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          invested_value: Number(form.invested_value),
          current_value: Number(form.current_value),
        }),
      });

      notify("Portfolio asset saved.");
      setForm({
        asset: "",
        asset_type: "Savings",
        invested_value: "",
        current_value: "",
      });

      await load();
    } catch (err) {
      notify(err.message);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ASSETS AND SAVINGS</p>
          <h1>Portfolio Intelligence</h1>
        </div>
      </div>

      <div className="metrics-grid">
        <Card title="Invested" value={money(portfolio?.total_invested)} />
        <Card title="Current value" value={money(portfolio?.current_value)} />
        <Card title="Profit / loss" value={money(portfolio?.profit_loss)} />
        <Card title="Return" value={`${portfolio?.return_percentage || 0}%`} />
      </div>

      <section className="card">
        <h2>Add savings or an asset</h2>
        <form className="form grid-form" onSubmit={submit}>
          <label>
            Asset name
            <input
              value={form.asset}
              onChange={(e) => setForm({ ...form, asset: e.target.value })}
              placeholder="Emergency savings"
              required
            />
          </label>

          <label>
            Asset type
            <select
              value={form.asset_type}
              onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            >
              <option>Savings</option>
              <option>Fixed Deposit</option>
              <option>Mutual Fund</option>
              <option>Stock</option>
              <option>Gold</option>
              <option>Other</option>
            </select>
          </label>

          <label>
            Invested value (₹)
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.invested_value}
              onChange={(e) => setForm({ ...form, invested_value: e.target.value })}
              required
            />
          </label>

          <label>
            Current value (₹)
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.current_value}
              onChange={(e) => setForm({ ...form, current_value: e.target.value })}
              required
            />
          </label>

          <button className="primary">Save asset</button>
        </form>
      </section>

      <section className="card">
        <h2>Portfolio assets</h2>
        {portfolio?.assets?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Invested</th>
                  <th>Current value</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.assets.map((a) => (
                  <tr key={a.id}>
                    <td>{a.asset}</td>
                    <td>{a.asset_type}</td>
                    <td>{money(a.invested_value)}</td>
                    <td>{money(a.current_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No assets recorded yet.</p>
        )}

        {(portfolio?.risk_warnings || []).map((warning) => (
          <div className="notice" key={warning}>{warning}</div>
        ))}
      </section>
    </>
  );
}

function RiskAnalysis({ notify }) {
  const [form, setForm] = useState({
    income: "",
    debt: "0",
    monthly_expenses: "",
    credit_utilization: "0",
    repayment_score: "75",
    savings: "0",
  });

  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);

    try {
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [key, Number(value)])
      );

      setResult(await api("/api/risk/credit-score", {
        method: "POST",
        body: JSON.stringify(payload),
      }));
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">FINANCIAL HEALTH</p>
          <h1>Risk Analysis</h1>
        </div>
      </div>

      <section className="card">
        <h2>Assess your financial indicators</h2>
        <form className="form grid-form" onSubmit={submit}>
          {[
            ["income", "Monthly income (₹)"],
            ["debt", "Total debt (₹)"],
            ["monthly_expenses", "Monthly expenses (₹)"],
            ["credit_utilization", "Credit utilization (%)"],
            ["repayment_score", "Repayment score (0–100)"],
            ["savings", "Savings (₹)"],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                type="number"
                min="0"
                step="0.01"
                max={key === "credit_utilization" || key === "repayment_score" ? "100" : undefined}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                required
              />
            </label>
          ))}

          <button className="primary" disabled={busy}>
            {busy ? "Calculating..." : "Analyze financial risk"}
          </button>
        </form>
      </section>

      {result && (
        <section className="card">
          <p className="eyebrow">RESULT</p>
          <h2>{result.risk_category}</h2>
          <div className="large-score">{result.risk_score}/100</div>
          <p>Debt-to-income: {(result.debt_to_income * 100).toFixed(1)}%</p>
          <p>Expense-to-income: {(result.expense_to_income * 100).toFixed(1)}%</p>
          <p>Savings-to-income: {(result.savings_ratio * 100).toFixed(1)}%</p>
          <p className="muted tiny">{result.disclaimer}</p>
        </section>
      )}
    </>
  );
}

function FraudIntelligence({ alerts, refresh }) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">SECURITY CENTER</p>
          <h1>Fraud Intelligence</h1>
          <p className="muted">
            Review transactions flagged by the configured screening rules.
          </p>
        </div>

        <button className="secondary" onClick={refresh}>Refresh alerts</button>
      </div>

      {!alerts.length ? (
        <section className="card">
          <h2>No flagged transactions</h2>
          <p className="muted">
            No transactions currently meet the configured alert thresholds.
            This does not guarantee that every transaction is safe.
          </p>
        </section>
      ) : (
        alerts.map((t) => {
          let reasons = t.risk_factors;

          if (typeof reasons === "string") {
            try {
              reasons = JSON.parse(reasons);
            } catch {
              reasons = [reasons];
            }
          }

          return (
            <section className="card fraud-card" key={t.id}>
              <div className="row-between">
                <div>
                  <span className="status high-risk">{t.decision}</span>
                  <h2>{t.category}</h2>
                  <p className="muted">{t.location} · {t.device}</p>
                </div>
                <strong>{money(t.amount)}</strong>
              </div>

              <p>Risk score: {Number(t.risk_score || 0)}/100</p>
              <h3>Why it was flagged</h3>
              <ul>
                {(Array.isArray(reasons) ? reasons : []).map((reason, i) => (
                  <li key={`${t.id}-${i}`}>{reason}</li>
                ))}
              </ul>

              <p className="muted tiny">
                Verify this transaction through your bank's official app or
                support channel if you do not recognize it.
              </p>
            </section>
          );
        })
      )}
    </>
  );
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(Boolean(readToken()));
  const [section, setSection] = useState("Dashboard");
  const [dashboard, setDashboard] = useState({});
  const [transactions, setTransactions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [toast, setToast] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);

  function notify(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 6000);
  }

  async function refresh() {
    if (!readToken()) return;

    setLoading(true);

    try {
      const [dash, tx, fraud] = await Promise.all([
        api("/api/dashboard"),
        api("/api/transactions"),
        api("/api/fraud/alerts"),
      ]);

      setDashboard(dash);
      setTransactions(tx);
      setAlerts(fraud);
    } catch (err) {
      if (/expired|invalid token|log in/i.test(err.message)) {
        sessionStorage.removeItem("finsight_token");
        setLoggedIn(false);
      }
      notify(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (loggedIn) refresh();
  }, [loggedIn, refreshKey]);

  useEffect(() => {
    if (!loggedIn) return;

    const timer = window.setInterval(refresh, 30000);
    return () => window.clearInterval(timer);
  }, [loggedIn]);

  function logout() {
    sessionStorage.removeItem("finsight_token");
    setLoggedIn(false);
    setDashboard({});
    setTransactions([]);
    setAlerts([]);
    setSection("Dashboard");
  }

  if (!loggedIn) {
    return <AuthScreen onLogin={() => setLoggedIn(true)} />;
  }

  const sections = [
    ["Dashboard", "▦"],
    ["Transactions", "⇄"],
    ["Risk Analysis", "◈"],
    ["Portfolio Intelligence", "◉"],
    ["Fraud Intelligence", "⌁"],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark small-mark">F</div>
          <div>
            <strong>FinSight</strong>
            <small>Financial intelligence</small>
          </div>
        </div>

        <nav>
          {sections.map(([name, icon]) => (
            <button
              key={name}
              className={section === name ? "nav-item selected" : "nav-item"}
              onClick={() => setSection(name)}
            >
              <span>{icon}</span>
              {name}
              {name === "Fraud Intelligence" && alerts.length > 0 && (
                <span className="count">{alerts.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span className="live-dot" />
          <span>Personal workspace</span>
          <button className="logout" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <span className="muted">Your financial workspace</span>
          <div className="topbar-right">
            {loading && <span className="muted">Updating…</span>}
            <button className="secondary compact" onClick={() => setRefreshKey((n) => n + 1)}>
              Refresh
            </button>
          </div>
        </header>

        {toast && (
          <button className="toast" onClick={() => setToast("")}>
            {toast} <span>×</span>
          </button>
        )}

        <div className="content">
          {section === "Dashboard" && (
            <Dashboard dashboard={dashboard} transactions={transactions} />
          )}

          {section === "Transactions" && (
            <Transactions
              transactions={transactions}
              refresh={refresh}
              notify={notify}
            />
          )}

          {section === "Risk Analysis" && (
            <RiskAnalysis notify={notify} />
          )}

          {section === "Portfolio Intelligence" && (
            <Portfolio notify={notify} refreshKey={refreshKey} />
          )}

          {section === "Fraud Intelligence" && (
            <FraudIntelligence
              alerts={alerts}
              refresh={refresh}
            />
          )}
        </div>
      </main>
    </div>
  );
}
