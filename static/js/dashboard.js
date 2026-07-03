(function () {
  const EMOTION_KO = {
    angry: "분노",
    disgust: "혐오",
    fear: "불안",
    happy: "기쁨",
    sad: "슬픔",
    surprise: "놀람",
    neutral: "평온",
  };

  const EMOTION_EMOJI = {
    angry: "😤",
    disgust: "😣",
    fear: "😰",
    happy: "😊",
    sad: "😢",
    surprise: "😲",
    neutral: "😌",
  };

  const BOT_AVATAR = "🤖";
  const DEFAULT_SITUATION = "general_support";

  let lastFusion = { fused_emotion: "neutral", situation: "general_support" };
  let lastAnalyzeAt = 0;
  let statusTimer = null;
  let manualEmotion = null;

  function scrollChatToBottom() {
    const box = document.getElementById("chatMessages");
    if (!box) return;
    requestAnimationFrame(() => {
      box.scrollTop = box.scrollHeight;
    });
  }

  function setStatus(msg, isError = false) {
    const el = document.getElementById("dashStatus");
    if (!el) return;
    clearTimeout(statusTimer);
    if (!msg) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.hidden = false;
    el.textContent = msg;
    el.style.color = isError ? "#d98585" : "";
    if (!isError) {
      statusTimer = setTimeout(() => setStatus(""), 3500);
    }
  }

  function updateChatEmotionBadge(emotion, emotionKo) {
    const badge = document.getElementById("chatEmotionBadge");
    const emojiEl = document.getElementById("chatEmotionEmoji");
    const labelEl = document.getElementById("chatEmotionLabel");
    if (!badge || !emojiEl || !labelEl) return;
    const em = emotion || "neutral";
    emojiEl.textContent = EMOTION_EMOJI[em] || "💬";
    labelEl.textContent = emotionKo || EMOTION_KO[em] || "평온";
    badge.hidden = false;
  }

  function syncManualEmotionUi() {
    document.querySelectorAll(".emotion-choice-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.emotion === manualEmotion);
    });
    const clearBtn = document.getElementById("clearEmotionChoiceBtn");
    if (clearBtn) clearBtn.hidden = !manualEmotion;
  }

  function applyEmotionChoice(emotion, source = "manual") {
    const chosen = emotion || "neutral";
    lastFusion = {
      ...lastFusion,
      fused_emotion: chosen,
      situation: lastFusion.situation || DEFAULT_SITUATION,
    };
    updateChatEmotionBadge(chosen, EMOTION_KO[chosen] || "평온");
    if (source === "manual") {
      manualEmotion = chosen;
      syncManualEmotionUi();
      setStatus(`${EMOTION_EMOJI[chosen] || ""} ${EMOTION_KO[chosen] || "평온"} 기분으로 챗봇에 반영할게요.`);
    }
  }

  function clearManualEmotion() {
    manualEmotion = null;
    syncManualEmotionUi();
    updateChatEmotionBadge(
      lastFusion.fused_emotion,
      EMOTION_KO[lastFusion.fused_emotion] || "평온"
    );
    setStatus("자동 표정 분석 결과를 다시 사용합니다.");
  }

  function updateLiveChip(visual, fusion, shouldShow = true) {
    const chip = document.getElementById("liveEmotionChip");
    const emojiEl = document.getElementById("liveEmotionEmoji");
    const label = document.getElementById("liveEmotionLabel");
    const conf = document.getElementById("liveEmotionConf");
    if (!chip || !visual) return;

    const emo = fusion?.fused_emotion || visual.emotion;
    const emoKo =
      fusion?.fused_emotion_ko ||
      visual.emotion_ko ||
      EMOTION_KO[emo] ||
      "";
    const confVal = fusion?.confidence ?? visual.confidence ?? 0;

    if (emojiEl) emojiEl.textContent = EMOTION_EMOJI[emo] || "";
    label.textContent = emoKo;
    conf.textContent = `${Math.round(confVal * 100)}%`;
    chip.hidden = !shouldShow;
    if (shouldShow) {
      chip.classList.add("chip-flash");
      setTimeout(() => chip.classList.remove("chip-flash"), 600);
    }

    if (!manualEmotion) {
      updateChatEmotionBadge(emo, emoKo);
    }
  }

  function hideLiveChip() {
    const chip = document.getElementById("liveEmotionChip");
    const emojiEl = document.getElementById("liveEmotionEmoji");
    const label = document.getElementById("liveEmotionLabel");
    const conf = document.getElementById("liveEmotionConf");
    if (emojiEl) emojiEl.textContent = "";
    if (label) label.textContent = "";
    if (conf) conf.textContent = "";
    if (chip) chip.hidden = true;
  }

  function getChatBox() {
    return document.getElementById("chatMessages");
  }

  function getTypingEl() {
    return document.getElementById("chatTyping");
  }

  /** 타이핑(...)은 항상 대화 맨 아래(최신 메시지 다음)에 위치 */
  function ensureTypingAtBottom() {
    const box = getChatBox();
    const typing = getTypingEl();
    if (box && typing && typing.parentElement === box) {
      box.appendChild(typing);
    }
  }

  function insertChatMessage(node) {
    const box = getChatBox();
    const typing = getTypingEl();
    if (!box) return;
    if (typing && typing.parentElement === box) {
      box.insertBefore(node, typing);
    } else {
      box.appendChild(node);
    }
  }

  function showTyping(show) {
    const el = getTypingEl();
    if (!el) return;
    ensureTypingAtBottom();
    el.hidden = !show;
    el.setAttribute("aria-hidden", show ? "false" : "true");
    if (show) scrollChatToBottom();
  }

  async function loadSession() {
    try {
      const res = await fetch("/api/session");
      const data = await res.json();
      if (data.logged_in && data.profile) {
        document.getElementById("displayName").textContent = data.profile.display_name;
        renderMoodHistory(data.profile.mood_history || []);
        restoreChatHistory(data.chat_history || []);
      }
    } catch (_) {
      /* ignore */
    }
  }

  function prependMoodChip(emotion) {
    const panel = document.getElementById("moodHistoryPanel");
    const list = document.getElementById("moodHistoryList");
    if (!panel || !list || !emotion) return;
    panel.hidden = false;
    const chip = document.createElement("span");
    chip.className = "mood-chip";
    chip.textContent = `${EMOTION_EMOJI[emotion] || "💬"} ${EMOTION_KO[emotion] || emotion}`;
    list.prepend(chip);
    while (list.children.length > 8) {
      list.removeChild(list.lastChild);
    }
  }

  function renderMoodHistory(moods) {
    const panel = document.getElementById("moodHistoryPanel");
    const list = document.getElementById("moodHistoryList");
    if (!panel || !list) return;

    const recent = moods.slice(-8).reverse();
    if (!recent.length) {
      panel.hidden = true;
      list.innerHTML = "";
      return;
    }

    panel.hidden = false;
    list.innerHTML = recent
      .map((emo) => {
        const label = EMOTION_KO[emo] || emo;
        const emoji = EMOTION_EMOJI[emo] || "💬";
        return `<span class="mood-chip">${emoji} ${escapeHtml(label)}</span>`;
      })
      .join("");
  }

  function restoreChatHistory(history) {
    if (!history.length) return;

    const box = getChatBox();
    const typing = getTypingEl();
    if (!box) return;

    box.querySelectorAll(".msg:not(.chat-typing)").forEach((node) => node.remove());

    history.forEach((item) => {
      const content = (item.content || "").trim();
      if (!content) return;
      if (item.role === "user") {
        appendUserMessage(content);
      } else if (item.role === "assistant") {
        appendBotMessage(content);
      }
    });

    if (typing && typing.parentElement !== box) {
      box.appendChild(typing);
    }
    ensureTypingAtBottom();
    scrollChatToBottom();
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
    setTimeout(() => {
      if (overlay) overlay.hidden = true;
    }, 2500);
  }

  function applyEmotionResult(data, options = {}) {
    const { revealChip = true } = options;
    const visual = data.visual;
    const fusion = data.fusion;
    lastFusion = {
      fused_emotion: fusion.fused_emotion,
      situation: fusion.situation,
    };
    lastAnalyzeAt = Date.now();
    updateLiveChip(visual, fusion, revealChip);
    showFaceBox(visual.face_box);
    prependMoodChip(fusion?.fused_emotion || visual.emotion);
    const label =
      fusion.fused_emotion_ko ||
      visual.emotion_ko ||
      EMOTION_KO[fusion.fused_emotion];
    const em = EMOTION_EMOJI[fusion.fused_emotion] || "";
    if (manualEmotion) {
      updateChatEmotionBadge(manualEmotion, EMOTION_KO[manualEmotion] || "평온");
      setStatus(`표정은 ${em} ${label}로 읽혔어요. 현재는 직접 고른 기분이 우선 적용됩니다.`);
    } else {
      setStatus(`표정 분석: ${em} ${label} (챗봇에 반영됨)`);
    }
  }

  async function runEmotionAnalyze(options = {}) {
    const { silent = false, revealChip = true } = options;
    const btn = document.getElementById("analyzeBtn");
    const syncBtn = document.getElementById("syncEmotionBtn");
    hideLiveChip();
    if (btn) {
      btn.disabled = true;
      btn.textContent = "분석 중…";
    }
    if (syncBtn) syncBtn.disabled = true;
    if (!silent) setStatus("표정 분석 중…");

    const img = await CameraHelper.captureDataUrl();
    const message = document.getElementById("chatInput")?.value?.trim() || "";

    if (!img) {
      setStatus("얼굴이 보이지 않습니다. 카메라 또는 '사진'을 이용해 주세요.", true);
      if (btn) {
        btn.disabled = false;
        btn.textContent = "표정 분석";
      }
      if (syncBtn) syncBtn.disabled = false;
      return false;
    }

    try {
      const data = await postJson("/api/emotion/analyze", { image: img, message });
      if (!data.success) {
        hideLiveChip();
        setStatus(data.error || "얼굴을 찾지 못했습니다. 정면을 바라봐 주세요.", true);
        return false;
      }
      applyEmotionResult(data, { revealChip });
      return true;
    } catch (err) {
      hideLiveChip();
      setStatus(err.message || "분석 요청에 실패했습니다.", true);
      return false;
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "표정 분석";
      }
      if (syncBtn) syncBtn.disabled = false;
    }
  }

  document.getElementById("analyzeBtn")?.addEventListener("click", () => {
    runEmotionAnalyze({ silent: false, revealChip: true });
  });
  document.getElementById("syncEmotionBtn")?.addEventListener("click", () => {
    runEmotionAnalyze({ silent: false, revealChip: false });
  });

  document.querySelectorAll(".emotion-choice-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyEmotionChoice(btn.dataset.emotion, "manual");
    });
  });

  document.getElementById("clearEmotionChoiceBtn")?.addEventListener("click", () => {
    clearManualEmotion();
  });

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

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "msg user";
    div.innerHTML = `<div class="msg-body"><p>${escapeHtml(text)}</p></div>`;
    insertChatMessage(div);
    scrollChatToBottom();
  }

  function appendBotMessage(text, meta = {}) {
    const avatar = meta.bot_avatar || BOT_AVATAR;
    const div = document.createElement("div");
    div.className = "msg bot";
    div.innerHTML = `
      <span class="msg-avatar" aria-hidden="true">${escapeHtml(avatar)}</span>
      <div class="msg-body"><p>${escapeHtml(text).replace(/\n/g, "<br>")}</p></div>
    `;
    insertChatMessage(div);
    scrollChatToBottom();
  }

  function resizeChatInput() {
    const input = document.getElementById("chatInput");
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");

  chatInput?.addEventListener("input", resizeChatInput);

  chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm?.requestSubmit();
    }
  });

  chatForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSendBtn");
    const text = input.value.trim();
    if (!text) return;

    appendUserMessage(text);
    input.value = "";
    resizeChatInput();
    if (sendBtn) sendBtn.disabled = true;
    showTyping(true);

    if (Date.now() - lastAnalyzeAt > 45000) {
      await runEmotionAnalyze({ silent: true, revealChip: false });
    }

    try {
      const activeEmotion = manualEmotion || lastFusion.fused_emotion;
      const data = await postJson("/api/chat", {
        message: text,
        fused_emotion: activeEmotion,
        situation: lastFusion.situation,
      });
      showTyping(false);
      if (data.success) {
        appendBotMessage(data.reply, {
          bot_avatar: data.bot_avatar,
          emotion_emoji: data.emotion_emoji,
        });
        if (data.emotion_ko) {
          updateChatEmotionBadge(data.emotion, data.emotion_ko);
        }
      } else {
        appendBotMessage(data.error || "응답을 생성하지 못했습니다.");
      }
    } catch (err) {
      showTyping(false);
      appendBotMessage(err.message || "챗봇 서버에 연결할 수 없습니다.");
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  });

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/";
  });

  document.getElementById("deleteAccountBtn")?.addEventListener("click", async () => {
    const emailInput = document.getElementById("deleteAccountEmail");
    const errEl = document.getElementById("deleteAccountError");
    const btn = document.getElementById("deleteAccountBtn");
    const email = String(emailInput?.value || "").trim();

    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }

    if (
      !window.confirm(
        "정말 계정을 삭제할까요?\n얼굴 데이터와 대화 기록이 모두 삭제되며 되돌릴 수 없습니다."
      )
    ) {
      return;
    }

    if (!email) {
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = "이메일 주소를 입력해 주세요.";
      }
      emailInput?.focus();
      return;
    }

    if (btn) btn.disabled = true;
    try {
      const data = await postJson("/api/account/delete", { email });
      if (data.success) {
        window.location.href = "/";
        return;
      }
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = data.error || "계정 삭제에 실패했습니다.";
      }
    } catch (err) {
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = err.message || "서버 연결에 실패했습니다.";
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", async () => {
    hideLiveChip();
    setStatus("");
    updateChatEmotionBadge("neutral", "평온");
    syncManualEmotionUi();
    await CameraHelper.init("dashVideo", "dashCanvas");
    CameraHelper.bindGalleryButton(
      "galleryAnalyzeBtn",
      "galleryAnalyzeInput",
      "dashVideo",
      "dashStatus"
    );
    await loadSession();
    resizeChatInput();
    scrollChatToBottom();
  });
})();
