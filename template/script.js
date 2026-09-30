var form = document.getElementById("contact-form");
if (form) {
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var base = document.body.getAttribute("data-submit-base");
    var msg = "Заявка с сайта. Имя: " + document.getElementById("f-name").value.trim() +
      ". Телефон: " + document.getElementById("f-phone").value.trim() +
      ". " + document.getElementById("f-comment").value.trim();
    window.location.href = base + (base.indexOf("?") > -1 ? "&" : "?") +
      "text=" + encodeURIComponent(msg);
  });
}
