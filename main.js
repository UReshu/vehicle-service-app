document.addEventListener("DOMContentLoaded", () => {
    const alerts = document.querySelectorAll(".alert");
    if (!alerts.length) return;
    setTimeout(() => {
        alerts.forEach((a) => (a.style.display = "none"));
    }, 3500);
});
