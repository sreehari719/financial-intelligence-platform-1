import { useEffect, useState } from "react";
import "./style.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboard() {
    setLoading(true);
    setError("");

    try {
      const token = localStorage.getItem("access_token");

      const response = await fetch(`${API_URL}/api/dashboard`, {
        headers: {
          Accept: "application/json",
          ...(token
            ? { Authorization: `Bearer ${token}` }
            : {}),
        },
      });

      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Please log in to access your dashboard."
            : `Server error: ${response.status}`
        );
      }

      setData(await response.json());
    } catch (err) {
      setError(err.message || "Could not connect to the backend.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const getValue = (...keys) => {
    for (const key of keys) {
      if (data?.[key] !== undefined && data?.[key] !== null) {
        return data[key];
      }
    }
    return null;
  };

  const currency = (value) => {
    if (value === null || value === undefined) return "--";

    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);

    return number.toLocaleString("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    });
  };

  const cards = [
    {
      title: "Total Transactions",
      value: getValue("transaction_count", "total_transactions"),
      icon: "⇄",
      description: "Recorded transactions",
    },
    {
      title: "Transaction Value",
      value: currency(
        getValue("transaction_value", "total_transaction_value", "total")
      ),
      icon: "₹",
      description: "Total transaction amount",
    },
    {
      title: "Suspicious Activity",
      value: getValue(
        "suspicious_count",
        "suspicious_transactions",
        "fraud_count"
      ) ?? "--",
      icon: "⚠",
      description: "Flagged records",
    },
    {
      title: "Risk Status",
      value: getValue("risk_status", "risk_level", "overall_risk") ?? "--",
      icon: "◈",
      description: "Reported risk level",
    },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <h2 className="logo">
          Fin<span>Sight.</span>
        </h2>

        <p className="menu-title">WORKSPACE</p>

        <a className="nav-link active" href="#dashboard">▦ Dashboard</a>
        <a className="nav-link" href="#transactions">⇄ Transactions</a>
        <a className="nav-link" href="#risk">◈ Risk Analysis</a>
        <a className="nav-link" href="#portfolio">▤ Portfolio</a>
        <a className="nav-link" href="#fraud">⚠ Fraud Intelligence</a>

        <div className="sidebar-footer">
          <p>FINANCIAL INTELLIGENCE</p>
          <small>Analytics • Risk • Security</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1 id="dashboard">Financial Dashboard</h1>
            <p className="subtitle">
              Monitor transactions, portfolio performance and financial risk.
            </p>
          </div>

          <button
            className="refresh-button"
            onClick={loadDashboard}
            disabled={loading}
          >
            {loading ? "Loading..." : "↻ Refresh"}
          </button>
        </header>

        <section className={`status ${error ? "status-error" : ""}`}>
          <span className="status-dot" />
          <div>
            <strong>
              {loading
                ? "Connecting to backend"
                : error
                ? "Connection issue"
                : "Dashboard API connected"}
            </strong>
            <p>
              {loading
                ? "Fetching your financial data..."
                : error || "Data received from FastAPI."}
            </p>
          </div>
        </section>

        <section className="stats-grid">
          {cards.map((card) => (
            <article className="stat-card" key={card.title}>
              <div className="stat-top">
                <span>{card.title}</span>
                <span className="stat-icon">{card.icon}</span>
              </div>
              <h2>{loading ? "..." : card.value ?? "--"}</h2>
              <p>{card.description}</p>
            </article>
          ))}
        </section>

        <section className="panel" id="transactions">
          <div className="panel-header">
            <div>
              <h2>Backend Dashboard Data</h2>
              <p>Live response from your FastAPI endpoint</p>
            </div>
            <span className="live-badge">● API</span>
          </div>

          {error ? (
            <div className="empty-state">
              <h3>Unable to load data</h3>
              <p>{error}</p>
              <button onClick={loadDashboard}>Try Again</button>
            </div>
          ) : (
            <pre className="json-output">
              {loading
                ? "Loading dashboard data..."
                : JSON.stringify(data, null, 2)}
            </pre>
          )}
        </section>

        <section className="modules-grid">
          <article className="panel module" id="risk">
            <span className="module-icon">◈</span>
            <h2>Risk Analysis</h2>
            <p>Analyze customer risk and financial exposure.</p>
            <span className="module-status">Risk module</span>
          </article>

          <article className="panel module" id="portfolio">
            <span className="module-icon">▤</span>
            <h2>Portfolio Intelligence</h2>
            <p>Monitor investment allocation and performance.</p>
            <span className="module-status">Portfolio module</span>
          </article>

          <article className="panel module" id="fraud">
            <span className="module-icon">⚠</span>
            <h2>Fraud Intelligence</h2>
            <p>Identify suspicious transactions and fraud indicators.</p>
            <span className="module-status">Fraud module</span>
          </article>
        </section>

        <footer>
          FinSight © 2026 · Financial Risk & Intelligence Platform
        </footer>
      </main>
    </div>
  );
}