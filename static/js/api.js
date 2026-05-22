/** API 요청 (모바일·Render 슬립 대응) */
window.postJson = async function postJson(url, body, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
      signal: controller.signal,
    });

    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      if (res.status === 502 || res.status === 503) {
        throw new Error(
          "서버가 깨어나는 중입니다. 30초 후 새로고침하고 다시 시도해 주세요."
        );
      }
      throw new Error(`서버 오류 (${res.status}). 잠시 후 다시 시도해 주세요.`);
    }

    if (!res.ok && data.error === undefined) {
      data = { success: false, error: data.error || `요청 실패 (${res.status})` };
    }
    return data;
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(
        "응답이 너무 느립니다. Wi-Fi를 확인하고, 1분 후 다시 시도하거나 사진을 다시 선택해 주세요."
      );
    }
    if (err.message) throw err;
    throw new Error("네트워크 연결을 확인해 주세요.");
  } finally {
    clearTimeout(timer);
  }
};
