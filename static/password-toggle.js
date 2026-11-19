document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-password-toggle]").forEach((button) => {
        const inputId = button.getAttribute("aria-controls");
        const passwordInput = document.getElementById(inputId);

        if (!passwordInput) return;

        button.addEventListener("click", () => {
            const isRevealed = passwordInput.type === "password";
            passwordInput.type = isRevealed ? "text" : "password";
            button.textContent = isRevealed ? "Hide" : "Show";
            button.setAttribute("aria-label", `${isRevealed ? "Hide" : "Show"} password`);
            button.setAttribute("aria-pressed", String(isRevealed));
            passwordInput.focus({ preventScroll: true });
        });
    });
});
