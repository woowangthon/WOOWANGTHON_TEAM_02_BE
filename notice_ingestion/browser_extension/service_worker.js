const TARGETS = {
  computer: "https://computer.cbnu.ac.kr/",
  electrical: "https://koamma.cbnu.ac.kr/index.php",
};
const DEPARTMENT_NAMES = { computer: "컴퓨터공학과", electrical: "전기공학부" };
const EMPTY_BODY_LENGTH = 0;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "START_NOTICE_CHECK") {
    startCheck(message.department, message.apiBase)
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message?.type === "NOTICE_PAGE_READ") {
    handlePageRead(message, sender.tab?.id).catch((error) => finishWithError(error.message));
  }
  if (message?.type === "NOTICE_DETAIL_READ") {
    handleDetailRead(message.notice, sender.tab?.id).catch((error) => finishWithError(error.message));
  }
  if (message?.type === "NOTICE_IMPORT_SAVED") {
    handleImportSaved(message, sender.tab?.id).catch((error) => console.error("Notice tab cleanup failed", error));
  }
  return false;
});

async function startCheck(department, apiBase) {
  if (!TARGETS[department]) throw new Error("학과를 확인할 수 없습니다.");
  const normalizedApi = normalizeLocalApi(apiBase);
  const checkId = String(Date.now());
  const sourceTab = await chrome.tabs.create({ url: "about:blank", active: false });
  await chrome.storage.local.set({
    activeCheck: { checkId, tabId: sourceTab.id, department, apiBase: normalizedApi },
    lastCheck: { status: "checking", department, checkedAt: new Date().toISOString() },
    pendingImport: null,
  });
  await chrome.tabs.update(sourceTab.id, { url: TARGETS[department] });
  await chrome.tabs.create({ url: chrome.runtime.getURL("results.html"), active: true });
}

function normalizeLocalApi(value) {
  const parsed = new URL(value || "http://localhost:8000");
  if (parsed.protocol !== "http:" || !["localhost", "127.0.0.1"].includes(parsed.hostname) || !["8000", "8001"].includes(parsed.port)) {
    throw new Error("알려줌 주소는 localhost 또는 127.0.0.1의 8000/8001 포트여야 합니다.");
  }
  return parsed.origin;
}

async function handlePageRead(message, senderTabId) {
  const { activeCheck } = await chrome.storage.local.get("activeCheck");
  if (!activeCheck || activeCheck.tabId !== senderTabId || activeCheck.department !== message.department) return;
  if (!Array.isArray(message.notices) || message.notices.length === 0) {
    await finishWithError("현재 페이지에서 공지 목록을 찾지 못했습니다.");
    await closeSourcePage(senderTabId);
    return;
  }

  try {
    const known = await getKnownNoticeKeys(activeCheck.apiBase);
    const newNotices = message.notices.flatMap((notice) => {
      const key = keyFor(notice.department, notice.post_number);
      const alreadyStored = known.has(key);
      const contentLength = known.get(key) ?? 0;
      if (alreadyStored && contentLength > EMPTY_BODY_LENGTH) return [];
      return [{ ...notice, update_existing: alreadyStored }];
    });
    await chrome.storage.local.set({
      lastCheck: {
        status: "done",
        department: message.department,
        sourceUrl: message.sourceUrl,
        checkedAt: new Date().toISOString(),
        listCount: message.notices.length,
        newNotices,
        apiBase: activeCheck.apiBase,
        savedNotice: null,
      },
      activeCheck: null,
    });
  } catch (error) {
    await finishWithError(`DB 비교에 실패했습니다: ${error.message}`);
  } finally {
    await closeSourcePage(senderTabId);
  }
}

async function closeSourcePage(tabId) {
  if (!Number.isInteger(tabId)) return;
  try { await chrome.tabs.remove(tabId); } catch { /* it may already be closed */ }
}

async function handleDetailRead(notice, sourceTabId) {
  const { lastCheck } = await chrome.storage.local.get("lastCheck");
  if (!lastCheck || lastCheck.status !== "done" || !Array.isArray(lastCheck.newNotices)) return;
  const matched = lastCheck.newNotices.find((item) =>
    item.department === notice.department && item.post_number === notice.post_number
  );
  if (!matched) return;
  if (!notice.title || !notice.content || !notice.date) {
    await finishWithError("상세 글의 제목·본문·게시일을 모두 읽지 못했습니다.");
    return;
  }
  const { apiBase = "http://localhost:8000" } = lastCheck;
  await chrome.storage.local.set({
    pendingImport: {
      notice: { ...notice, update_existing: matched.update_existing },
      apiBase,
      sourceTabId,
    },
  });
  await chrome.tabs.create({ url: `${apiBase}/extension-import`, active: true });
}

async function handleImportSaved(message, importTabId) {
  const { pendingImport, lastCheck } = await chrome.storage.local.get(["pendingImport", "lastCheck"]);
  if (!pendingImport || pendingImport.notice.post_number !== message.post_number
      || pendingImport.notice.department !== message.department) return;

  await chrome.storage.local.set({
    pendingImport: null,
    lastCheck: {
      ...lastCheck,
      savedNotice: {
        post_number: message.post_number,
        department: message.department,
        update_existing: Boolean(pendingImport.notice.update_existing),
      },
    },
  });

  const tabsToClose = [...new Set([importTabId, pendingImport.sourceTabId].filter(Number.isInteger))];
  for (const tabId of tabsToClose) {
    try { await chrome.tabs.remove(tabId); } catch { /* the user may have closed it already */ }
  }
}

async function getKnownNoticeKeys(apiBase) {
  const first = await fetch(`${apiBase}/api/notices?page=1&per_page=100`, { headers: { Accept: "application/json" } });
  if (!first.ok) throw new Error(`알려줌 API 응답 ${first.status} (사이트 확인은 완료됨)`);
  const firstPage = await first.json();
  const rows = [...(firstPage.items || [])];
  const pages = Math.min(Number(firstPage.pages) || 1, 20);
  for (let page = 2; page <= pages; page += 1) {
    const response = await fetch(`${apiBase}/api/notices?page=${page}&per_page=100`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`알려줌 API 응답 ${response.status}`);
    const result = await response.json();
    rows.push(...(result.items || []));
  }
  return new Map(
    rows
      .map((row) => [keyFromStoredNotice(row), Number(row.content_length) || 0])
      .filter(([key]) => Boolean(key)),
  );
}

function keyFromStoredNotice(row) {
  const url = safeUrl(row.original_url);
  const postNumber = url?.searchParams.get("no");
  if (!postNumber) return "";
  const host = url.hostname.toLowerCase();
  let department = "";
  if (host.includes("computer") || String(row.department_name || row.source_name || "").includes("컴퓨터")) department = "computer";
  if (host.includes("koamma") || String(row.department_name || row.source_name || "").includes("전기")) department = "electrical";
  return department ? keyFor(department, postNumber) : "";
}

function keyFor(department, postNumber) {
  return `${department}|${postNumber}`;
}

function safeUrl(value) {
  try { return new URL(value); } catch { return null; }
}

async function finishWithError(error) {
  const current = await chrome.storage.local.get("lastCheck");
  await chrome.storage.local.set({
    lastCheck: { ...(current.lastCheck || {}), status: "error", error, checkedAt: new Date().toISOString() },
    activeCheck: null,
  });
}
