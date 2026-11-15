const apiInput = document.querySelector("#apiBase");
const statusLine = document.querySelector("#status");

chrome.storage.local.get({ apiBase: "http://localhost:8000" }).then(({ apiBase }) => {
  apiInput.value = apiBase;
});

document.querySelector("#saveApi").addEventListener("click", async () => {
  const value = apiInput.value.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(value);
    const isLocal = parsed.protocol === "http:"
      && ["localhost", "127.0.0.1"].includes(parsed.hostname)
      && ["8000", "8001"].includes(parsed.port);
    const isProduction = parsed.protocol === "https:"
      && parsed.hostname === "woowangthonteam02be-production.up.railway.app"
      && (!parsed.port || parsed.port === "443");
    if ((!isLocal && !isProduction) || parsed.username || parsed.password
        || (parsed.pathname !== "/" && parsed.pathname !== "") || parsed.search || parsed.hash) {
      throw new Error();
    }
    await chrome.storage.local.set({ apiBase: parsed.origin });
    statusLine.textContent = "알려줌 주소를 저장했습니다.";
  } catch {
    statusLine.textContent = "localhost:8000/8001 또는 공개 Railway 앱 주소를 입력해 주세요.";
  }
});

document.querySelectorAll("[data-department]").forEach((button) => {
  button.addEventListener("click", async () => {
    document.querySelectorAll("button").forEach((item) => { item.disabled = true; });
    statusLine.textContent = "확인 페이지를 여는 중입니다...";
    const apiBase = apiInput.value.trim().replace(/\/+$/, "");
    const response = await chrome.runtime.sendMessage({
      type: "START_NOTICE_CHECK",
      department: button.dataset.department,
      apiBase,
    });
    if (!response?.ok) {
      statusLine.textContent = response?.error || "확인을 시작하지 못했습니다.";
      document.querySelectorAll("button").forEach((item) => { item.disabled = false; });
    } else {
      window.close();
    }
  });
});
