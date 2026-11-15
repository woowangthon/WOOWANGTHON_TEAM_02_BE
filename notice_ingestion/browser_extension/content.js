(() => {
  const hostname = location.hostname.toLowerCase();
  if (["localhost", "127.0.0.1"].includes(hostname) && location.pathname === "/extension-import") {
    window.addEventListener("message", async (event) => {
      if (event.source !== window || event.origin !== location.origin) return;
      if (event.data?.source !== "cbnu-notice-extension" || event.data?.type !== "NOTICE_IMPORT_SAVED") return;
      const { pendingImport } = await chrome.storage.local.get("pendingImport");
      if (!pendingImport || pendingImport.notice.post_number !== event.data.post_number
          || pendingImport.notice.department !== event.data.department) return;
      chrome.runtime.sendMessage({
        type: "NOTICE_IMPORT_SAVED",
        post_number: event.data.post_number,
        department: event.data.department,
      });
    });
    chrome.storage.local.get("pendingImport").then(({ pendingImport }) => {
      if (!pendingImport) return;
      window.postMessage({
        source: "cbnu-notice-extension",
        type: "NOTICE_IMPORT_PREVIEW",
        payload: pendingImport.notice,
      }, location.origin);
    });
    return;
  }

  const department = hostname.includes("koamma") ? "electrical" : "computer";
  if (location.pathname === "/bbs/bbs.php") {
    const pageParams = new URLSearchParams(location.search);
    if (pageParams.get("task") === "view" && pageParams.get("db") === "notice") {
      sendDetail(department, pageParams.get("no"));
    }
    return;
  }

  const expectedPath = department === "electrical" ? "/index.php" : "/";
  if (location.pathname !== expectedPath) return;
  sendList(department);
})();

function sendList(department) {
  const notices = [];
  const seen = new Set();
  for (const anchor of document.querySelectorAll('a[href*="task=view"]')) {
    const url = new URL(anchor.href, location.href);
    if (url.searchParams.get("db") !== "notice") continue;
    const postNumber = url.searchParams.get("no");
    const row = anchor.closest("tr");
    if (!postNumber || !row || seen.has(postNumber)) continue;
    const titleCopy = anchor.cloneNode(true);
    titleCopy.querySelectorAll("img, svg").forEach((node) => node.remove());
    const title = (titleCopy.textContent || "").replace(/\s+/g, " ").trim();
    const dateMatch = (row.innerText || row.textContent || "").match(/\b\d{4}[-./]\s*\d{1,2}[-./]\s*\d{1,2}\b/);
    if (!title) continue;
    seen.add(postNumber);
    notices.push({
      post_number: postNumber,
      title,
      date: dateMatch ? dateMatch[0].replace(/\s/g, "") : "",
      url: url.href,
      department,
    });
  }
  chrome.runtime.sendMessage({
    type: "NOTICE_PAGE_READ",
    department,
    sourceUrl: location.href,
    notices,
  });
}

function sendDetail(department, postNumber) {
  const titleNode = document.querySelector(".view_subject");
  const article = document.querySelector("#articles");
  if (!postNumber || !titleNode || !article) return;
  const title = (titleNode.textContent || "").replace(/\s+/g, " ").trim();
  const author = (document.querySelector(".view_name")?.textContent || "").replace(/\s+/g, " ").trim();
  let date = "";
  for (const node of document.querySelectorAll(".view_text")) {
    const text = (node.innerText || node.textContent || "").replace(/\s+/g, " ");
    if (!text.includes("작성일")) continue;
    const match = text.match(/\d{4}[-./]\s*\d{1,2}[-./]\s*\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?/);
    if (match) date = match[0].replace(/\s*([./-])\s*/g, "$1");
    break;
  }
  const content = (article.innerText || article.textContent || "")
    .replace(/\u00a0/g, " ")
    .split("\n")
    .map((line) => line.replace(/[\t ]+/g, " ").trim())
    .filter(Boolean)
    .join("\n")
    .trim();
  const attachments = [];
  const seenFiles = new Set();
  for (const anchor of document.querySelectorAll('a[href*="download.php"]')) {
    const url = new URL(anchor.href, location.href);
    if (url.searchParams.get("no") !== postNumber) continue;
    let name = (anchor.textContent || "").replace(/\s+/g, " ").trim();
    if (!name) {
      const image = anchor.querySelector("img");
      name = image?.alt || image?.title || "";
    }
    if (!name || seenFiles.has(url.href)) continue;
    seenFiles.add(url.href);
    attachments.push({ name, url: url.href });
  }

  chrome.runtime.sendMessage({
    type: "NOTICE_DETAIL_READ",
    notice: {
      department,
      post_number: postNumber,
      title,
      author,
      date,
      url: location.href,
      content,
      attachments,
    },
  });
}
