document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const drawer = document.getElementById("navDrawer");
  const links = document.querySelector(".nav-links");
  const guideBtn = document.getElementById("openGuideBtn");
  const appNav =
    document.querySelector("[data-nav-mode='app']") ||
    document.querySelector(".navbar--app");

  if (appNav && drawer && toggle) {
    const panel = drawer.querySelector(".nav-drawer-panel");
    let lastFocus = null;

    const openDrawer = () => {
      lastFocus = document.activeElement;
      drawer.hidden = false;
      drawer.setAttribute("aria-hidden", "false");
      requestAnimationFrame(() => {
        drawer.classList.add("open");
        toggle.setAttribute("aria-expanded", "true");
        document.body.classList.add("nav-drawer-open");
        panel?.focus();
      });
    };

    const closeDrawer = () => {
      drawer.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      document.body.classList.remove("nav-drawer-open");
      const onEnd = () => {
        drawer.hidden = true;
        drawer.setAttribute("aria-hidden", "true");
        panel?.removeEventListener("transitionend", onEnd);
      };
      if (panel) {
        panel.addEventListener("transitionend", onEnd, { once: true });
        setTimeout(onEnd, 350);
      } else {
        onEnd();
      }
      lastFocus?.focus?.();
    };

    toggle.addEventListener("click", () => {
      if (drawer.classList.contains("open")) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });

    drawer.querySelectorAll("[data-nav-close]").forEach((el) => {
      el.addEventListener("click", closeDrawer);
    });

    guideBtn?.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawer.classList.contains("open")) {
        closeDrawer();
      }
    });

    return;
  }

  if (!toggle || !links) return;

  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  links.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => {
      links.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });

  guideBtn?.addEventListener("click", () => {
    links.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  });
});
