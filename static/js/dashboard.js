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
    container.innerHTML = "";
    const sorted = Object.entries(distribution || {}).sort((a, b) => b[1] - a[1]);

    sorted.forEach(([emo, val]) => {
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
      overlay.hidden = true;
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

  document.getElementById("analyzeBtn")?.addEventListener("click", async () => {
    const img = CameraHelper.captureDataUrl();
    const message = document.getElementById("chatInput")?.value || "";
    const btn = document.getElementById("analyzeBtn");
    btn.disabled = true;
    btn.textContent = "분석 중...";

    try {
      const res = await fetch("/api/emotion/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: img, message }),
      });
      const data = await res.json();

      if (!data.success) {
        appendBotMessage(data.error || "분석에 실패했습니다.");
        return;
      }

      const visual = data.visual;
      const fusion = data.fusion;
      lastFusion = {
        fused_emotion: fusion.fused_emotion,
        situation: fusion.situation,
      };

      document.getElementById("emotionResult").hidden = false;
      document.getElementById("emotionLabel").textContent =
        visual.emotion_ko || EMOTION_KO[visual.emotion];
      document.getElementById("emotionConfidence").textContent =
        `${Math.round(visual.confidence * 100)}% 신뢰도`;
      document.getElementById("fusedEmotion").textContent =
        fusion.fused_emotion_ko || EMOTION_KO[fusion.fused_emotion];
      document.getElementById("situation").textContent =
        SITUATION_KO[fusion.situation] || fusion.situation;

      renderEmotionBars(visual.distribution);
      showFaceBox(visual.face_box);
    } catch {
      appendBotMessage("서버와 연결할 수 없습니다.");
    } finally {
      btn.disabled = false;
      btn.textContent = "감정 분석하기";
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

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          fused_emotion: lastFusion.fused_emotion,
          situation: lastFusion.situation,
        }),
      });
      const data = await res.json();
      if (data.success) {
        appendBotMessage(data.reply);
      } else {
        appendBotMessage(data.error || "응답을 생성하지 못했습니다.");
      }
    } catch {
      appendBotMessage("챗봇 서버에 연결할 수 없습니다.");
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
      "dashCameraHint"
    );
    if (CameraHelper.isMobile?.()) {
      const hint = document.getElementById("dashCameraHint");
      if (hint) {
        hint.textContent =
          "모바일: PC와 같은 Wi-Fi에 연결한 뒤, run.bat에 표시된 주소로 접속하세요.";
      }
    }
    await loadSession();
  });
})();
