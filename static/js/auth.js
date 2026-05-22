const AuthHelper = (() => {
  let capturedFace = null;

  function showError(elId, msg) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || "";
  }

  function initRegister() {
    const captureBtn = document.getElementById("captureFaceBtn");
    const form = document.getElementById("registerForm");
    const status = document.getElementById("faceStatus");

    captureBtn?.addEventListener("click", async () => {
      CameraHelper.clearGalleryCapture?.();
      status.textContent = "사진 처리 중...";
      capturedFace = await CameraHelper.captureDataUrl();
      if (capturedFace) {
        status.textContent = "얼굴 촬영 완료! 가입을 진행하세요.";
        status.style.color = "#55efc4";
      } else {
        status.textContent = "촬영에 실패했습니다. '사진 촬영/선택'을 이용해 주세요.";
        status.style.color = "#ff7675";
      }
    });

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("registerError", "");

      status.textContent = "사진 준비 중...";
      let faceImage = (await CameraHelper.captureDataUrl()) || capturedFace;
      if (!faceImage) {
        showError("registerError", "얼굴을 촬영하거나 '사진 촬영/선택'을 이용해 주세요.");
        status.textContent = "";
        return;
      }

      const fd = new FormData(form);
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      status.textContent = "서버에 가입 요청 중... (최대 1분)";

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
          status.textContent = "";
        }
      } catch (err) {
        showError("registerError", err.message || "서버 연결에 실패했습니다.");
        status.textContent = "";
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
      showError("loginError", "");
      status.textContent = "얼굴 인식 중...";

      const img = await CameraHelper.captureDataUrl();
      if (!img) {
        showError("loginError", "사진을 가져올 수 없습니다. '사진 촬영/선택'을 이용해 주세요.");
        status.textContent = "";
        return;
      }

      try {
        const data = await postJson("/api/login/face", { face_image: img });
        if (data.success) {
          status.textContent = `인식 성공 (${(data.match_score * 100).toFixed(0)}%)`;
          window.location.href = "/dashboard";
        } else {
          showError("loginError", data.error || "로그인 실패");
          status.textContent = "";
        }
      } catch (err) {
        showError("loginError", err.message || "서버 연결에 실패했습니다.");
        status.textContent = "";
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
      } catch (err) {
        showError("loginError", err.message || "서버 연결에 실패했습니다.");
      }
    });
  }

  return { initRegister, initLogin };
})();
