(function () {
  const EMOTION_KO = {
    angry: "분노", disgust: "혐오", fear: "불안", happy: "기쁨",
    sad: "슬픔", surprise: "놀람", neutral: "평온",
  };

  const SITUATION_KO = {
    celebration: "기쁨 나누기",
    casual_positive: "편안한 대화",
    comfort_needed: "위로 필요",
    gentle_support: "부드러운 지지",
    de_escalation: "감정 완화",
    reassurance: "안심·격려",
    neutral_chat: "일상 대화",
    excited_chat: "활기찬 대화",
    general_support: "일반 지원",
  };

  let lastFusion = { fused_emotion: "neutral", situation: "general_support" };
  let lastAnalyzeAt = 0;

  function setStatus(msg, isError = false) {
    const el = document.getElementById("dashStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = isError ? "#ff7675" : "";
  }

  function updateLiveChip(visual) {
    const chip = document.getElementById("liveEmotionChip");
    const label = document.getElementById("liveEmotionLabel");
    const conf = document.getElementById("liveEmotionConf");
    if (!chip || !visual) return;
    chip.hidden = false;
    label.textContent = visual.emotion_ko || EMOTION_KO[visual.emotion] || "—";
    conf.textContent = `${Math.round((visual.confidence || 0) * 100)}%`;
  }

  async function loadSession() {
    try {
      const res = await fetch("/api/session");
      const data = await res.json();
      if (data.logged_in && data.profile) {
        document.getElementById("displayName").textContent = data.profile.display_name;
      }
    } catch (_) { /* ignore */ }
  }

  function renderEmotionBars(distribution) {
    const container = document.getElementById("emotionBars");
    if (!container) return;
    container.innerHTML = "";
    const sorted = Object.entries(distribution || {}).sort((a, b) => b[1] - a[1]);
    sorted.slice(0, 5).forEach(([emo, val]) => {
      const pct = Math.round(val * 100);
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <span>${EMOTION_KO[emo] || emo}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <span>${pct}%</span>
      `;
      container.appendChild(row);
    });
  }

  function showFaceBox(box) {
    const overlay = document.getElementById("faceOverlay");
    const wrap = document.querySelector(".dash-camera");
    if (!box || !wrap) {
      if (overlay) overlay.hidden = true;
      return;
    }
    const video = document.getElementById("dashVideo");
    const scaleX = wrap.clientWidth / (video.videoWidth || 640);
    const scaleY = wrap.clientHeight / (video.videoHeight || 480);
    overlay.style.left = `${box.x * scaleX}px`;
    overlay.style.top = `${box.y * scaleY}px`;
    overlay.style.width = `${box.w * scaleX}px`;
    overlay.style.height = `${box.h * scaleY}px`;
    overlay.hidden = false;
  }

  function applyEmotionResult(data) {
    const visual = data.visual;
    const fusion = data.fusion;
    lastFusion = {
      fused_emotion: fusion.fused_emotion,
      situation: fusion.situation,
    };
    lastAnalyzeAt = Date.now();

    document.getElementById("emotionResult").hidden = false;
    document.getElementById("emotionLabel").textContent =
      visual.emotion_ko || EMOTION_KO[visual.emotion];
    document.getElementById("emotionConfidence").textContent =
      `${Math.round(visual.confidence * 100)}%`;
    document.getElementById("fusedEmotion").textContent =
      fusion.fused_emotion_ko || EMOTION_KO[fusion.fused_emotion];
    document.getElementById("situation").textContent =
      SITUATION_KO[fusion.situation] || fusion.situation;

    updateLiveChip(visual);
    renderEmotionBars(visual.distribution);
    showFaceBox(visual.face_box);
    setStatus("표정이 반영되었습니다. 이제 메시지를 보내 보세요.");
  }

  async function runEmotionAnalyze(silent = false) {
    const btn = document.getElementById("analyzeBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "분석 중…";
    }
    if (!silent) setStatus("표정 분석 중…");

    const img = await CameraHelper.captureDataUrl();
    const message = document.getElementById("chatInput")?.value?.trim() || "";

    if (!img) {
      const msg = "얼굴이 보이지 않습니다. 카메라 권한을 허용하거나 '사진' 버튼을 사용해 주세요.";
      setStatus(msg, true);
      if (btn) {
        btn.disabled = false;
        btn.textContent = "표정 분석";
      }
      return false;
    }

    try {
      const data = await postJson("/api/emotion/analyze", { image: img, message });
      if (!data.success) {
        setStatus(data.error || "얼굴을 찾지 못했습니다. 정면을 바라봐 주세요.", true);
        return false;
      }
      applyEmotionResult(data);
      return true;
    } catch (err) {
      setStatus(err.message || "분석 요청에 실패했습니다.", true);
      return false;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "표정 분석";
      }
    }
  }

  document.getElementById("analyzeBtn")?.addEventListener("click", () => runEmotionAnalyze(false));

  document.getElementById("refaceBtn")?.addEventListener("click", async () => {
    setStatus("얼굴 재등록 중…");
    const img = await CameraHelper.captureDataUrl();
    if (!img) {
      setStatus("얼굴 사진을 가져올 수 없습니다.", true);
      return;
    }
    try {
      const data = await postJson("/api/face/update", { face_image: img });
      if (data.success) {
        setStatus(data.message || "얼굴이 새로 등록되었습니다.");
      } else {
        setStatus(data.error || "재등록에 실패했습니다.", true);
      }
    } catch (err) {
      setStatus(err.message || "재등록 요청 실패", true);
    }
  });

  function appendUserMessage(text) {
    const box = document.getElementById("chatMessages");
    const div = document.createElement("div");
    div.className = "msg user";
    div.innerHTML = `<p>${escapeHtml(text)}</p>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function appendBotMessage(text) {
    const box = document.getElementById("chatMessages");
    const div = document.createElement("div");
    div.className = "msg bot";
    div.innerHTML = `<p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  document.getElementById("chatForm")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (!text) return;

    appendUserMessage(text);
    input.value = "";

    if (Date.now() - lastAnalyzeAt > 45000) {
      setStatus("메시지와 함께 표정을 분석합니다…");
      await runEmotionAnalyze(true);
    }

    try {
      const data = await postJson("/api/chat", {
        message: text,
        fused_emotion: lastFusion.fused_emotion,
        situation: lastFusion.situation,
      });
      if (data.success) {
        appendBotMessage(data.reply);
        setStatus("");
      } else {
        appendBotMessage(data.error || "응답을 생성하지 못했습니다.");
      }
    } catch (err) {
      appendBotMessage(err.message || "챗봇 서버에 연결할 수 없습니다.");
    }
  });

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/";
  });

  document.addEventListener("DOMContentLoaded", async () => {
    await CameraHelper.init("dashVideo", "dashCanvas");
    CameraHelper.bindGalleryButton(
      "galleryAnalyzeBtn",
      "galleryAnalyzeInput",
      "dashVideo",
      "dashStatus"
    );
    await loadSession();
    setStatus("정면을 보면서 대화해 보세요. 필요하면 '표정 분석'을 누르세요.");
  });
})();
