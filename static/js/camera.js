/**
 * 웹캠 / 모바일 갤러리 · 셀카 촬영
 */
const CameraHelper = (() => {
  let stream = null;
  let videoEl = null;
  let canvasEl = null;
  let lastDataUrl = null;

  const isMobile = () =>
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
    window.matchMedia("(max-width: 768px)").matches;

  function getVideoConstraints() {
    if (isMobile()) {
      return {
        facingMode: "user",
        width: { ideal: 1280, max: 1920 },
        height: { ideal: 720, max: 1080 },
      };
    }
    return {
      facingMode: "user",
      width: { ideal: 640 },
      height: { ideal: 480 },
    };
  }

  async function init(videoId, canvasId) {
    videoEl = document.getElementById(videoId);
    canvasEl = document.getElementById(canvasId);
    if (!videoEl) return false;

    if (!navigator.mediaDevices?.getUserMedia) {
      showCameraHint(
        "이 브라우저는 카메라를 지원하지 않습니다. 아래 '사진 선택'을 이용해 주세요."
      );
      return false;
    }

    try {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
      }
      stream = await navigator.mediaDevices.getUserMedia({
        video: getVideoConstraints(),
        audio: false,
      });
      videoEl.srcObject = stream;
      videoEl.setAttribute("playsinline", "true");
      videoEl.setAttribute("webkit-playsinline", "true");
      await videoEl.play();
      return true;
    } catch (err) {
      console.error("카메라 접근 실패:", err);
      const msg = isMobile()
        ? "카메라를 쓸 수 없습니다. '사진 촬영/선택' 버튼을 이용해 주세요. (iPhone은 Safari에서 같은 Wi-Fi 주소 접속 시 카메라가 제한될 수 있어요)"
        : "카메라 권한을 허용해 주세요.";
      showCameraHint(msg);
      return false;
    }
  }

  function showCameraHint(message) {
    const status = document.querySelector(
      ".status-text, #loginFaceStatus, #faceStatus, #dashCameraHint"
    );
    if (status) {
      status.textContent = message;
      status.style.color = "#ff7675";
    }
  }

  function captureDataUrl() {
    if (lastDataUrl) return lastDataUrl;
    if (!videoEl || !canvasEl) return null;
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    if (!w || !h) return null;

    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvasEl.toDataURL("image/jpeg", 0.82);
  }

  function setFromFile(file, previewVideoId) {
    return new Promise((resolve, reject) => {
      if (!file || !file.type.startsWith("image/")) {
        reject(new Error("이미지 파일만 선택할 수 있습니다."));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        lastDataUrl = reader.result;
        const preview = document.getElementById(previewVideoId);
        if (preview && preview.tagName === "VIDEO") {
          const wrap = preview.parentElement;
          let img = wrap.querySelector(".preview-img");
          if (!img) {
            img = document.createElement("img");
            img.className = "preview-img";
            img.alt = "선택한 사진";
            wrap.appendChild(img);
          }
          img.src = lastDataUrl;
          img.style.display = "block";
          preview.style.display = "none";
        }
        resolve(lastDataUrl);
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  function clearGalleryCapture() {
    lastDataUrl = null;
  }

  function bindGalleryButton(buttonId, inputId, previewVideoId, statusId) {
    const btn = document.getElementById(buttonId);
    const input = document.getElementById(inputId);
    if (!btn || !input) return;

    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        clearGalleryCapture();
        await setFromFile(file, previewVideoId);
        const status = statusId ? document.getElementById(statusId) : null;
        if (status) {
          status.textContent = "사진이 준비되었습니다.";
          status.style.color = "#55efc4";
        }
      } catch (e) {
        showCameraHint(e.message || "사진을 불러오지 못했습니다.");
      }
      input.value = "";
    });
  }

  return {
    init,
    captureDataUrl,
    setFromFile,
    clearGalleryCapture,
    bindGalleryButton,
    isMobile,
  };
})();
