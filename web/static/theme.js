/**
 * Feynman Check — Theme Controller (Light / Dark Mode)
 * Persists user preference in localStorage with system preference fallback.
 */

function getPreferredTheme() {
  const saved = localStorage.getItem("fc_theme");
  if (saved) return saved;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme) {
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  updateThemeToggleLabels(theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  const next = current === "light" ? "dark" : "light";
  localStorage.setItem("fc_theme", next);
  applyTheme(next);
}

function updateThemeToggleLabels(theme) {
  const isLight = theme === "light";
  const buttons = document.querySelectorAll(".theme-toggle-btn");
  buttons.forEach((btn) => {
    const iconEl = btn.querySelector(".theme-icon");
    const textEl = btn.querySelector(".theme-toggle-text");
    if (iconEl) iconEl.textContent = isLight ? "🌙" : "☀️";
    if (textEl) textEl.textContent = isLight ? "Dark" : "Light";
    btn.setAttribute("title", isLight ? "Switch to Dark Mode" : "Switch to Light Mode");
    btn.setAttribute("aria-label", isLight ? "Switch to Dark Mode" : "Switch to Light Mode");
  });
}

// Initial sync once DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  updateThemeToggleLabels(current);
});
