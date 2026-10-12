document.addEventListener("DOMContentLoaded", () => {
  const forms = document.querySelectorAll("form");
  forms.forEach(form => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit'], button:not([type])");
      if (button && !form.classList.contains("login-form")) {
        button.dataset.originalText = button.textContent;
      }
    });
  });
});
