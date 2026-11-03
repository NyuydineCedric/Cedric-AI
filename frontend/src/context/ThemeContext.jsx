import { createContext, useContext, useEffect, useState } from "react";

// -----------------------------------------------------------------------
// Cedric AI - Theme Context (UI redesign)
// -----------------------------------------------------------------------
// Persists light/dark preference to localStorage and applies it as a
// data-theme attribute on <html>, which every CSS custom property in
// App.css branches on. Kept separate from AuthContext - this is a
// device preference, not account data, so it deliberately isn't sent
// to the backend or tied to the logged-in user.
// -----------------------------------------------------------------------

const THEME_STORAGE_KEY = "cedric_theme";
const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem(THEME_STORAGE_KEY) || "light",
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "light" ? "dark" : "light"));
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside a <ThemeProvider>");
  return ctx;
}
