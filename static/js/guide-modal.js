/**
 * 이용 방법 팝업 — 최초 1회 자동 표시, 이후 「이용 방법」 버튼으로 열기/닫기
 */
(function () {
  const STORAGE_KEY = "emotionai_guide_seen";
  const modal = document.getElementById("guideModal");
  const openBtn = document.getElementById("openGuideBtn");

  if (!modal) return;

  function isOpen() {
    return !modal.hidden;
  }

  function openGuide() {
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("guide-modal-open");
    const panel = modal.querySelector(".guide-modal-panel");
    if (panel) panel.focus();
  }

  function closeGuide(markSeen) {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("guide-modal-open");
    if (markSeen) {
      try {
        localStorage.setItem(STORAGE_KEY, "1");
      } catch (_) { /* ignore */ }
    }
  }

  function toggleGuide() {
    if (isOpen()) closeGuide(false);
    else openGuide();
  }

  modal.querySelectorAll("[data-guide-close]").forEach((el) => {
    el.addEventListener("click", () => closeGuide(true));
  });

  modal.addEventListener("click", (e) => {
    if (e.target.classList.contains("guide-modal-backdrop")) {
      closeGuide(true);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) closeGuide(true);
  });

  if (openBtn) {
    openBtn.addEventListener("click", (e) => {
      e.preventDefault();
      toggleGuide();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    let seen = false;
    try {
      seen = localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_) { /* ignore */ }
    if (!seen) {
      setTimeout(openGuide, 400);
    }
  });
})();
