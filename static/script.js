document.addEventListener("DOMContentLoaded", function () {
  const flashMessages = document.querySelectorAll(".flash-msg");
  if (flashMessages) {
    flashMessages.forEach((msg) => {
      setTimeout(() => {
        msg.style.opacity = "0";
        msg.style.transition = "opacity 0.6s ease";
        setTimeout(() => msg.remove(), 600);
      }, 4000);
    });
  }
  const machineryForm = document.querySelector("#equipmentForm");
  if (machineryForm) {
    machineryForm.addEventListener("submit", function (e) {
      const price = parseFloat(
        document.querySelector('input[name="price"]').value,
      );
      const stock = parseInt(
        document.querySelector('input[name="stock"]').value,
      );

      if (price <= 0) {
        alert(
          "Database Constraint Error: Machinery prices must be positive numeric assignments!",
        );
        e.preventDefault();
      }
      if (stock < 0) {
        alert(
          "Database Constraint Error: Inventory stock levels cannot fall below baseline zero values.",
        );
        e.preventDefault();
      }
    });
  }
});
