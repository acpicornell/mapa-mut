/* Light/dark theme, as on the sibling sites (corpusbalear portal, cronicon,
   llinatges-actuals).

   Loaded synchronously in <head>: the stored choice is applied before the first
   paint, or the page would flash in the system theme before switching. It is
   a file rather than an inline block, as on the sibling sites.

   data-theme="light"|"dark" on <html>; absent means "follow the system"
   (prefers-color-scheme). The button is wired here so it works on every page
   of the site, whatever else the page loads. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "mut-theme";
  try {
    var stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") root.setAttribute("data-theme", stored);
  } catch (e) { /* storage blocked: follow the system */ }

  function wire() {
    var button = document.getElementById("theme");
    if (!button) return;
    button.addEventListener("click", function () {
      var showing = root.getAttribute("data-theme") ||
        (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark" : "light");
      var next = showing === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* not remembered */ }
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
