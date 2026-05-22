const AuthHelper = (() => {
  let capturedFace = null;

  const EMOTION_KO = {
    angry: "분노", disgust: "혐오", fear: "불안", happy: "기쁨",
    sad: "슬픔", surprise: "놀람", neutral: "평온",
  };

  function showError(elId, msg) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || "";
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  }

  function initRegister() {
    const captureBtn = document.getElementById("captureFaceBtn");
    const form = document.getElementById("registerForm");
    const status = document.getElementById("faceStatus");

    captureBtn?.addEventListener("click", () => {
      CameraHelper.clearGalleryCapture?.();
      capturedFace = CameraHelper.captureDataUrl();
      if (capturedFace) {
        status.textContent = "얼굴 촬영 완료! 가입을 진행하세요.";
        status.style.color = "#55efc4";
      } else {
        status.textContent = "촬영에 실패했습니다. 카메라를 확인해 주세요.";
      }
    });

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("registerError", "");

      const faceImage = CameraHelper.captureDataUrl() || capturedFace;
      if (!faceImage) {
        showError("registerError", "얼굴을 촬영하거나 사진을 선택해 주세요.");
        return;
      }

      const fd = new FormData(form);
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;

      try {
        const data = await postJson("/api/register", {
          username: fd.get("username"),
          password: fd.get("password"),
          display_name: fd.get("display_name"),
          face_image: faceImage,
        });

        if (data.success) {
          window.location.href = "/dashboard";
        } else {
          showError("registerError", data.error || "가입에 실패했습니다.");
        }
      } catch {
        showError("registerError", "서버 연결에 실패했습니다.");
      } finally {
        btn.disabled = false;
      }
    });
  }

  function initLogin() {
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(`tab-${tab.dataset.tab}`)?.classList.add("active");
      });
    });

    document.getElementById("faceLoginBtn")?.addEventListener("click", async () => {
      const status = document.getElementById("loginFaceStatus");
      const img = CameraHelper.captureDataUrl();
      if (!img) {
        showError("loginError", "카메라에서 이미지를 가져올 수 없습니다.");
        return;
      }

      status.textContent = "얼굴 인식 중...";
      showError("loginError", "");

      try {
        const data = await postJson("/api/login/face", { face_image: img });
        if (data.success) {
          status.textContent = `인식 성공 (일치도 ${(data.match_score * 100).toFixed(0)}%)`;
          window.location.href = "/dashboard";
        } else {
          showError("loginError", data.error || "로그인 실패");
          status.textContent = "";
        }
      } catch {
        showError("loginError", "서버 연결에 실패했습니다.");
      }
    });

    document.getElementById("passwordLoginForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("loginError", "");
      const fd = new FormData(e.target);

      try {
        const data = await postJson("/api/login/password", {
          username: fd.get("username"),
          password: fd.get("password"),
        });
        if (data.success) {
          window.location.href = "/dashboard";
        } else {
          showError("loginError", data.error || "로그인 실패");
        }
      } catch {
        showError("loginError", "서버 연결에 실패했습니다.");
      }
    });
  }

  return { initRegister, initLogin };
})();
