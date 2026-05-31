const AuthHelper = (() => {
  let capturedFace = null;

  const FORBIDDEN_PW = new Set(["*", "&", '"']);
  const SPECIAL_PW =
    /[!@#$%^()_+\-=[\]{}|;:',.<>?/\\`~]/;

  function validatePassword(password) {
    if (!password || password.length < 8) {
      return "비밀번호는 8자 이상이어야 합니다.";
    }
    for (const c of password) {
      if (FORBIDDEN_PW.has(c)) {
        return '비밀번호에 *, &, " 문자는 사용할 수 없습니다.';
      }
    }
    if (!SPECIAL_PW.test(password)) {
      return '비밀번호에 특수문자를 1개 이상 포함해 주세요 (*, &, " 제외).';
    }
    return null;
  }

  function showError(elId, msg) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || "";
  }

  function setStatus(elId, msg, color = "") {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = color;
  }

  function initPasswordToggles(root = document) {
    root.querySelectorAll(".password-toggle-btn").forEach((btn) => {
      if (btn.dataset.bound === "true") return;
      btn.dataset.bound = "true";
      btn.addEventListener("click", () => {
        const wrap = btn.closest(".password-input-wrap");
        const input = wrap?.querySelector("input");
        if (!input) return;
        const visible = input.type === "text";
        input.type = visible ? "password" : "text";
        btn.textContent = visible ? "보기" : "숨김";
        btn.setAttribute("aria-label", visible ? "비밀번호 보기" : "비밀번호 숨기기");
        btn.setAttribute("aria-pressed", visible ? "false" : "true");
      });
    });
  }

  function initRegister() {
    initPasswordToggles();
    const captureBtn = document.getElementById("captureFaceBtn");
    const form = document.getElementById("registerForm");
    const status = document.getElementById("faceStatus");
    const emailInput = form?.querySelector('input[name="email"]');
    const emailCodeInput = form?.querySelector('input[name="email_code"]');
    const sendCodeBtn = document.getElementById("sendSignupCodeBtn");
    const verifyCodeBtn = document.getElementById("verifySignupCodeBtn");
    let verifiedEmail = "";

    const normalizeEmail = (value) => String(value || "").trim().toLowerCase();

    emailInput?.addEventListener("input", () => {
      const nextEmail = normalizeEmail(emailInput.value);
      if (!nextEmail) {
        verifiedEmail = "";
        setStatus("registerEmailStatus", "");
        return;
      }
      if (verifiedEmail && nextEmail !== verifiedEmail) {
        verifiedEmail = "";
        setStatus("registerEmailStatus", "이메일이 변경되어 다시 인증이 필요합니다.");
      }
    });

    captureBtn?.addEventListener("click", async () => {
      CameraHelper.clearGalleryCapture?.();
      status.textContent = "사진 처리 중...";
      capturedFace = await CameraHelper.captureDataUrl();
      if (capturedFace) {
        status.textContent = "얼굴 촬영 완료! 가입을 진행하세요.";
        status.style.color = "#8ec9b0";
      } else {
        status.textContent = "촬영에 실패했습니다. '사진 촬영/선택'을 이용해 주세요.";
        status.style.color = "#d98585";
      }
    });

    let signupCodeCooldownTimer = null;

    function startSignupCodeCooldown(seconds = 45) {
      if (!sendCodeBtn) return;
      let remain = seconds;
      sendCodeBtn.disabled = true;
      const defaultLabel = sendCodeBtn.textContent;
      const tick = () => {
        if (remain <= 0) {
          sendCodeBtn.disabled = false;
          sendCodeBtn.textContent = defaultLabel;
          signupCodeCooldownTimer = null;
          return;
        }
        sendCodeBtn.textContent = `다시 받기 (${remain}초)`;
        remain -= 1;
        signupCodeCooldownTimer = window.setTimeout(tick, 1000);
      };
      tick();
    }

    async function requestSignupVerificationEmail(email) {
      showError("registerError", "");
      if (!email) {
        showError("registerError", "이메일 주소를 먼저 입력해 주세요.");
        emailInput?.focus();
        return;
      }
      if (signupCodeCooldownTimer) return;
      sendCodeBtn.disabled = true;
      setStatus("registerEmailStatus", "인증번호를 준비 중입니다... (비밀번호 재설정과 동일)");
      try {
        const data = await postJson("/api/register/email-code/request", { email });
        if (data.success) {
          verifiedEmail = "";
          setStatus(
            "registerEmailStatus",
            data.message ||
              "입력한 이메일로 인증번호를 보냈습니다. 비밀번호 재설정 메일과 같은 형식입니다.",
            "#8ec9b0"
          );
          emailCodeInput?.focus();
          startSignupCodeCooldown(45);
          return;
        }
        showError("registerError", data.error || "인증번호 요청에 실패했습니다.");
        setStatus("registerEmailStatus", "");
        sendCodeBtn.disabled = false;
      } catch (err) {
        showError("registerError", err.message || "서버 연결에 실패했습니다.");
        setStatus("registerEmailStatus", "");
        sendCodeBtn.disabled = false;
      }
    }

    sendCodeBtn?.addEventListener("click", async () => {
      const email = normalizeEmail(emailInput?.value);
      await requestSignupVerificationEmail(email);
    });

    verifyCodeBtn?.addEventListener("click", async () => {
      showError("registerError", "");
      const email = normalizeEmail(emailInput?.value);
      const code = String(emailCodeInput?.value || "").trim();
      if (!email) {
        showError("registerError", "이메일 주소를 먼저 입력해 주세요.");
        emailInput?.focus();
        return;
      }
      if (!code) {
        showError("registerError", "이메일 인증번호를 입력해 주세요.");
        emailCodeInput?.focus();
        return;
      }
      verifyCodeBtn.disabled = true;
      setStatus("registerEmailStatus", "인증번호를 확인하는 중입니다...");
      try {
        const data = await postJson("/api/register/email-code/verify", { email, code });
        if (data.success) {
          verifiedEmail = email;
          setStatus("registerEmailStatus", data.message || "이메일 인증이 완료되었습니다.", "#8ec9b0");
        } else {
          showError("registerError", data.error || "이메일 인증에 실패했습니다.");
          setStatus("registerEmailStatus", "");
        }
      } catch (err) {
        showError("registerError", err.message || "서버 연결에 실패했습니다.");
        setStatus("registerEmailStatus", "");
      } finally {
        verifyCodeBtn.disabled = false;
      }
    });

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("registerError", "");
      const normalizedEmail = normalizeEmail(emailInput?.value);
      if (!normalizedEmail || normalizedEmail !== verifiedEmail) {
        showError("registerError", "이메일 인증을 완료해 주세요.");
        emailCodeInput?.focus();
        return;
      }

      const fd = new FormData(form);
      const password = fd.get("password") || "";
      const pwdErr = validatePassword(password);
      if (pwdErr) {
        showError("registerError", pwdErr);
        status.textContent = "";
        return;
      }

      status.textContent = "사진 준비 중...";
      let faceImage = (await CameraHelper.captureDataUrl()) || capturedFace;
      if (!faceImage) {
        showError("registerError", "얼굴을 촬영하거나 '사진 촬영/선택'을 이용해 주세요.");
        status.textContent = "";
        return;
      }

      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      status.textContent = "서버에 가입 요청 중... (최대 1분)";

      try {
        const data = await postJson("/api/register", {
          username: fd.get("username"),
          email: normalizedEmail,
          password,
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
    initPasswordToggles();
    const faceUsernameInput = document.getElementById("faceLoginUsername");
    const passwordUsernameInput = document.querySelector(
      '#passwordLoginForm input[name="username"]'
    );

    const syncUsername = (source, target) => {
      source?.addEventListener("input", () => {
        if (target && !target.value) {
          target.value = source.value;
        }
      });
    };

    syncUsername(faceUsernameInput, passwordUsernameInput);
    syncUsername(passwordUsernameInput, faceUsernameInput);

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
      const btn = document.getElementById("faceLoginBtn");
      const username = (faceUsernameInput?.value || "").trim();
      showError("loginError", "");
      status.textContent = "얼굴 인식 중... (최대 1분)";
      if (btn) btn.disabled = true;

      if (!username) {
        showError("loginError", "사용자 이름을 입력해 주세요.");
        status.textContent = "";
        if (btn) btn.disabled = false;
        faceUsernameInput?.focus();
        return;
      }

      const img = await CameraHelper.captureDataUrl();
      if (!img) {
        showError("loginError", "사진을 가져올 수 없습니다. '사진 촬영/선택'을 이용해 주세요.");
        status.textContent = "";
        if (btn) btn.disabled = false;
        return;
      }

      try {
        const data = await postJson(
          "/api/login/face",
          { username, face_image: img },
          120000
        );
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
      } finally {
        if (btn) btn.disabled = false;
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
          window.location.href = data.redirect_to || "/dashboard";
        } else {
          showError("loginError", data.error || "로그인 실패");
        }
      } catch (err) {
        showError("loginError", err.message || "서버 연결에 실패했습니다.");
      }
    });
  }

  function initForgotPassword() {
    initPasswordToggles();
    const requestForm = document.getElementById("forgotPasswordForm");
    const codeForm = document.getElementById("resetPasswordByCodeForm");
    const codeBtn = document.getElementById("sendResetCodeBtn");
    const verifyCodeBtn = document.getElementById("verifyResetCodeBtn");
    const submitCodeBtn = document.getElementById("resetPasswordByCodeSubmitBtn");
    const codeEmailInput = codeForm?.querySelector('input[name="email"]');
    const codeValueInput = codeForm?.querySelector('input[name="code"]');
    let verifiedResetCode = "";

    const resetCodeVerificationState = (message = "") => {
      verifiedResetCode = "";
      if (submitCodeBtn) submitCodeBtn.disabled = true;
      setStatus("forgotPasswordCodeStatus", message);
    };

    const buildResetCodeSignature = () =>
      `${String(codeEmailInput?.value || "").trim().toLowerCase()}::${String(codeValueInput?.value || "").trim()}`;

    codeEmailInput?.addEventListener("input", () => {
      if (verifiedResetCode && verifiedResetCode !== buildResetCodeSignature()) {
        resetCodeVerificationState("이메일이 변경되어 다시 인증이 필요합니다.");
      }
    });

    codeValueInput?.addEventListener("input", () => {
      if (verifiedResetCode && verifiedResetCode !== buildResetCodeSignature()) {
        resetCodeVerificationState("인증번호가 변경되어 다시 인증이 필요합니다.");
      }
    });

    async function requestResetMail(email, mode = "link") {
      showError("forgotPasswordError", "");
      setStatus(
        "forgotPasswordStatus",
        mode === "code" ? "인증번호를 준비 중입니다..." : "재설정 링크를 준비 중입니다..."
      );

      try {
        const data = await postJson("/api/password-reset/request", { email });
        if (data.success) {
          const successMsg =
            mode === "code"
              ? "입력한 이메일로 인증번호를 보냈습니다. 계정이 없다면 메일이 오지 않을 수 있습니다."
              : (data.message || "이메일을 확인해 주세요.");
          setStatus("forgotPasswordStatus", successMsg, "#8ec9b0");
          codeForm?.querySelector('input[name="email"]')?.setAttribute("value", email);
          const emailInput = codeForm?.querySelector('input[name="email"]');
          if (emailInput) emailInput.value = email;
          if (mode === "code") {
            resetCodeVerificationState("");
            codeForm?.querySelector('input[name="code"]')?.focus();
          }
        } else {
          showError("forgotPasswordError", data.error || "재설정 요청에 실패했습니다.");
          setStatus("forgotPasswordStatus", "");
        }
      } catch (err) {
        showError("forgotPasswordError", err.message || "서버 연결에 실패했습니다.");
        setStatus("forgotPasswordStatus", "");
      }
    }

    requestForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await requestResetMail(fd.get("email"), "link");
    });

    codeBtn?.addEventListener("click", async () => {
      const email = codeForm?.querySelector('input[name="email"]')?.value || "";
      if (!String(email).trim()) {
        showError("forgotPasswordError", "이메일 주소를 먼저 입력해 주세요.");
        setStatus("forgotPasswordStatus", "");
        codeForm?.querySelector('input[name="email"]')?.focus();
        return;
      }
      await requestResetMail(email, "code");
    });

    verifyCodeBtn?.addEventListener("click", async () => {
      showError("forgotPasswordError", "");
      const email = String(codeEmailInput?.value || "").trim();
      const code = String(codeValueInput?.value || "").trim();
      if (!email) {
        showError("forgotPasswordError", "이메일 주소를 먼저 입력해 주세요.");
        codeEmailInput?.focus();
        return;
      }
      if (!code) {
        showError("forgotPasswordError", "이메일 인증번호를 입력해 주세요.");
        codeValueInput?.focus();
        return;
      }

      verifyCodeBtn.disabled = true;
      setStatus("forgotPasswordCodeStatus", "이메일 인증번호를 확인하는 중입니다...");
      try {
        const data = await postJson("/api/password-reset/verify-code", { email, code });
        if (data.success) {
          verifiedResetCode = buildResetCodeSignature();
          if (submitCodeBtn) submitCodeBtn.disabled = false;
          setStatus("forgotPasswordCodeStatus", "이메일 인증번호가 일치합니다. 새 비밀번호를 설정해 주세요.", "#8ec9b0");
        } else {
          resetCodeVerificationState("");
          showError("forgotPasswordError", data.error || "이메일 인증번호 확인에 실패했습니다.");
        }
      } catch (err) {
        resetCodeVerificationState("");
        showError("forgotPasswordError", err.message || "서버 연결에 실패했습니다.");
      } finally {
        verifyCodeBtn.disabled = false;
      }
    });

    codeForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("forgotPasswordError", "");
      setStatus("forgotPasswordStatus", "");
      const fd = new FormData(e.target);
      if (!verifiedResetCode || verifiedResetCode !== buildResetCodeSignature()) {
        showError("forgotPasswordError", "이메일 인증번호 확인을 먼저 완료해 주세요.");
        codeValueInput?.focus();
        return;
      }
      const password = fd.get("password") || "";
      const confirm = fd.get("password_confirm") || "";

      if (password !== confirm) {
        showError("forgotPasswordError", "비밀번호 확인이 일치하지 않습니다.");
        return;
      }

      const pwdErr = validatePassword(password);
      if (pwdErr) {
        showError("forgotPasswordError", pwdErr);
        return;
      }

      setStatus("forgotPasswordStatus", "비밀번호를 변경하는 중입니다...");
      try {
        const data = await postJson("/api/password-reset/confirm-code", {
          email: fd.get("email"),
          code: fd.get("code"),
          password,
        });
        if (data.success) {
          setStatus("forgotPasswordStatus", data.message || "비밀번호가 재설정되었습니다.", "#8ec9b0");
          e.target.reset();
          setTimeout(() => {
            window.location.href = "/login";
          }, 1000);
        } else {
          showError("forgotPasswordError", data.error || "인증번호 확인에 실패했습니다.");
          setStatus("forgotPasswordStatus", "");
        }
      } catch (err) {
        showError("forgotPasswordError", err.message || "서버 연결에 실패했습니다.");
        setStatus("forgotPasswordStatus", "");
      }
    });
  }

  function initResetPassword() {
    initPasswordToggles();
    const form = document.getElementById("resetPasswordForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("resetPasswordError", "");
      setStatus("resetPasswordStatus", "");
      const fd = new FormData(form);
      const password = fd.get("password") || "";
      const confirm = fd.get("password_confirm") || "";

      if (password !== confirm) {
        showError("resetPasswordError", "비밀번호 확인이 일치하지 않습니다.");
        return;
      }

      const pwdErr = validatePassword(password);
      if (pwdErr) {
        showError("resetPasswordError", pwdErr);
        return;
      }

      setStatus("resetPasswordStatus", "비밀번호를 변경하는 중입니다...");
      try {
        const data = await postJson("/api/password-reset/confirm", {
          selector: fd.get("selector"),
          token: fd.get("token"),
          password,
        });
        if (data.success) {
          setStatus("resetPasswordStatus", data.message || "비밀번호가 재설정되었습니다.", "#8ec9b0");
          form.reset();
          setTimeout(() => {
            window.location.href = "/login";
          }, 1000);
        } else {
          showError("resetPasswordError", data.error || "비밀번호 변경에 실패했습니다.");
          setStatus("resetPasswordStatus", "");
        }
      } catch (err) {
        showError("resetPasswordError", err.message || "서버 연결에 실패했습니다.");
        setStatus("resetPasswordStatus", "");
      }
    });
  }

  return { initRegister, initLogin, initForgotPassword, initResetPassword };
})();
