import { useEffect, useState } from "react";
import "./App.css";
import { API_BASE_URL, apiFetch } from "./api/client";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ThemeProvider, useTheme } from "./context/ThemeContext";
import { AuthForm } from "./components/AuthForm";
import { ChatPanel } from "./components/ChatPanel";
import { DocumentsPanel } from "./components/DocumentsPanel";

import { MemoryPanel } from "./components/MemoryPanel";

import { QuizPanel } from "./components/QuizPanel";

const TABS = [
  { id: "chat", label: "Chat" },
  { id: "documents", label: "Documents" },
  { id: "memory", label: "Memory" },
  { id: "quiz", label: "Quiz" },
];

function AuthenticatedView() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [activeTab, setActiveTab] = useState("chat");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">Cedric AI</div>

        <nav className="sidebar-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`sidebar-link ${activeTab === tab.id ? "sidebar-link-active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button type="button" className="theme-toggle" onClick={toggleTheme}>
            {theme === "light" ? "☾ Dark mode" : "☀ Light mode"}
          </button>
          <div className="sidebar-user">{user.email}</div>
          <button
            type="button"
            className="submit-btn secondary"
            onClick={logout}
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="main-content-inner">
          {activeTab === "chat" && <ChatPanel />}
          {activeTab === "documents" && <DocumentsPanel />}

          {activeTab === "memory" && <MemoryPanel />}
          {activeTab === "quiz" && <QuizPanel />}
        </div>
      </main>
    </div>
  );
}

function LoginScreen() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="page">
      <div className="card">
        <button
          type="button"
          className="theme-toggle"
          style={{ marginBottom: "1.25rem" }}
          onClick={toggleTheme}
        >
          {theme === "light" ? "☾ Dark mode" : "☀ Light mode"}
        </button>
        <span className="eyebrow">Cedric AI</span>
        <h1>Sign in to continue</h1>
        <p className="lede">Create an account or log in.</p>
        <AuthForm />
      </div>
    </div>
  );
}

function AppShell() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="page">
        <div className="card">
          <p className="lede">Loading…</p>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <AuthenticatedView /> : <LoginScreen />;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
