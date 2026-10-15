// Loaded at the end of <body>, so the Sections button and the pane already exist. The pane starts hidden in
// index.html: without this script the page shows as before and its links still work.
(function () {
  "use strict";

  var button = document.querySelector(".nav-toggle");
  var pane = document.getElementById(button.getAttribute("aria-controls"));

  button.addEventListener("click", function () {
    var expanded = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(expanded));
    pane.hidden = !expanded;
  });
})();
