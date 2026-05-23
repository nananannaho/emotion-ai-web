/**
 * 웹캠 / 모바일 갤러리 · 업로드용 이미지 압축
 */
const CameraHelper = (() => {
  let stream = null;
  let videoEl = null;
  let canvasEl = null;
  let lastDataUrl = null;

  const MAX_UPLOAD_WIDTH = 480;
  const JPEG_QUALITY = 0.68;

  const isMobile = () =>
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
    window.matchMedia("(max-width: 768px)").matches;

  function getVideoConstraints() {
    if (isMobile()) {
      return {
        facingMode: "user",
        width: { ideal: 640, max: 1280 },
        height: { ideal: 480, max: 720 },
      };
    }
    return {
      facingMode: "user",
      width: { ideal: 640 },
      height: { ideal: 480 },
    };
  }

  function compressDataUrl(dataUrl, maxWidth = MAX_UPLOAD_WIDTH, quality = JPEG_QUALITY) {
    return new Promise((resolve) => {
      if (!dataUrl) {
        resolve(null);
        return;
      }
      const img = new Image();
      img.onload = () => {
        let w = img.width;
        let h = img.height;
        if (w > maxWidth) {
          h = Math.round((h * maxWidth) / w);
          w = maxWidth;
        }
        const c = document.createElement("canvas");
        c.width = w;
        c.height = h;
        const ctx = c.getContext("2d");
        ctx.translate(w, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL("image/jpeg", quality));
      };
      img.onerror = () => resolve(dataUrl);
      img.src = dataUrl;
    });
  }

  async function prepareForUpload(dataUrl) {
    if (!dataUrl) return null;
    return compressDataUrl(dataUrl);
  }

  async function init(videoId, canvasId) {
    videoEl = document.getElementById(videoId);
    canvasEl = document.getElementById(canvasId);
    if (!videoEl) return false;

    if (!navigator.mediaDevices?.getUserMedia) {
      showCameraHint(
        "이 브라우저는 카메라를 지원하지 않습니다. '사진 촬영/선택'을 이용해 주세요."
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
      showCameraHint(
        "카메라를 쓸 수 없습니다. '사진 촬영/선택' 버튼으로 등록해 주세요."
      );
      return false;
    }
  }

  function showCameraHint(message) {
    const status = document.querySelector(
      ".status-text, #loginFaceStatus, #faceStatus, #dashCameraHint"
    );
    if (status) {
      status.textContent = message;
      status.style.color = "#d98585";
    }
  }

  async function captureDataUrl() {
    if (lastDataUrl) return prepareForUpload(lastDataUrl);
    if (!videoEl || !canvasEl) return null;
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    if (!w || !h) return null;

    const scale = w > MAX_UPLOAD_WIDTH ? MAX_UPLOAD_WIDTH / w : 1;
    const cw = Math.round(w * scale);
    const ch = Math.round(h * scale);

    canvasEl.width = cw;
    canvasEl.height = ch;
    const ctx = canvasEl.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.translate(cw, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(videoEl, 0, 0, cw, ch);
    return prepareForUpload(canvasEl.toDataURL("image/jpeg", JPEG_QUALITY));
  }

  async function setFromFile(file, previewVideoId) {
    if (!file || !file.type.startsWith("image/")) {
      throw new Error("이미지 파일만 선택할 수 있습니다.");
    }
    const raw = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    lastDataUrl = await compressDataUrl(raw);

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
    return lastDataUrl;
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
          status.textContent = "사진 준비 완료. 가입을 진행하세요.";
          status.style.color = "#8ec9b0";
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
    prepareForUpload,
    isMobile,
  };
})();
