// Loaded from <head> before the body exists: the saved theme is set on <html> now, and the button is wired
// once the page is parsed. Without this script the page stays in the light theme and keeps working.
(function () {
  "use strict";

  var KEY = "theme";
  var root = document.documentElement;

  function savedTheme() {
    try {
      return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
    } catch (error) {
      return "light";
    }
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem(KEY, theme);
    } catch (error) {
      // Storage can be blocked by privacy settings; the switch still works until the page is closed.
    }
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    var button = document.querySelector(".theme-toggle");
    if (button) {
      button.setAttribute("aria-pressed", String(theme === "dark"));
    }
  }

  applyTheme(savedTheme());

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.querySelector(".theme-toggle");
    applyTheme(root.getAttribute("data-theme"));
    button.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      saveTheme(next);
    });
  });
})();
