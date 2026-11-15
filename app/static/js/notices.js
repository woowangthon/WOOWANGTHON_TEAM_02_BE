const statusNode = document.querySelector("#feed-status");
const listNode = document.querySelector("#notice-list");
const searchInput = document.querySelector("#notice-search");
const tabs = [...document.querySelectorAll(".feed-tab")];
const todayDate = document.querySelector("#today-date");
const menuToggle = document.querySelector("[data-menu-toggle]");
const mobileMenu = document.querySelector("[data-mobile-menu]");
const noticeDialog = document.querySelector("#notice-dialog");
const noticeDialogSource = noticeDialog?.querySelector("[data-notice-source]");
const noticeDialogTitle = noticeDialog?.querySelector("[data-notice-title]");
const noticeDialogDate = noticeDialog?.querySelector("[data-notice-date]");
const noticeDialogSummary = noticeDialog?.querySelector("[data-notice-summary]");
const noticeDialogContent = noticeDialog?.querySelector("[data-notice-content]");
const noticeDialogPlaceholder = noticeDialog?.querySelector("[data-notice-placeholder]");
const noticeDialogOriginal = noticeDialog?.querySelector("[data-notice-original]");
const summaryNote = noticeDialog?.querySelector("[data-summary-note]");
const summaryButton = noticeDialog?.querySelector("[data-ai-summary]");
const assistantDialog = document.querySelector("#assistant-dialog");
const chatMessages = assistantDialog?.querySelector("[data-chat-messages]");
const chatStatus = assistantDialog?.querySelector("[data-chat-status]");
let activeNoticeId = null;

let activeView = "all";
let notices = [];
let requestController;

if (todayDate) {
  const today = new Date();
  todayDate.dateTime = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  todayDate.textContent = new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "full",
  }).format(today);
}

menuToggle?.addEventListener("click", () => {
  const expanded = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!expanded));
  menuToggle.setAttribute("aria-label", expanded ? "메뉴 열기" : "메뉴 닫기");
  mobileMenu?.toggleAttribute("hidden", expanded);
});

function showMessage(message, className = "empty-state", description = "") {
  const note = document.createElement("div");
  note.className = className;

  const text = document.createElement("p");
  text.textContent = message;
  note.append(text);
  if (description) {
    const detail = document.createElement("p");
    detail.className = "empty-description";
    detail.textContent = description;
    note.append(detail);
  }
  listNode.replaceChildren(note);
}

function showLoginRequired() {
  const state = document.createElement("div");
  state.className = "empty-state login-required";

  const title = document.createElement("strong");
  title.textContent = "로그인이 필요합니다.";

  const description = document.createElement("p");
  description.textContent =
    activeView === "recommended"
      ? "학교, 학과·학부, 학년과 관심 분야를 기준으로 맞춤 공지를 보여드립니다."
      : activeView === "saved"
        ? "저장한 공지를 모아보려면 로그인해 주세요."
      : "내 학교의 공지 목록을 확인하려면 로그인해 주세요.";

  const link = document.createElement("button");
  link.className = "inline-login-link";
  link.type = "button";
  link.dataset.authOpen = "";
  link.textContent = "로그인하기";

  state.append(title, description, link);
  listNode.replaceChildren(state);
}

function formatDate(value) {
  if (!value) return "게시일 미상";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "게시일 미상";
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium" }).format(date);
}

async function openNoticeDetail(item) {
  if (!noticeDialog || !noticeDialogTitle) return;
  activeNoticeId = item.id;
  noticeDialogSource.textContent = item.source_name || "충북대학교 공지";
  noticeDialogTitle.textContent = item.title || "제목 없음";
  noticeDialogDate.textContent = formatDate(item.posted_at);
  noticeDialogSummary.textContent = "상세 내용을 불러오는 중입니다.";
  noticeDialogContent.replaceChildren();
  noticeDialogPlaceholder.hidden = true;
  noticeDialogOriginal.hidden = true;
  noticeDialog.showModal();

  try {
    const response = await fetch(`/api/notices/${encodeURIComponent(item.id)}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("notice_detail_failed");
    const detail = await response.json();
    const body = (detail.content || "").trim();
    const interimSummary = (detail.summary || "").trim();

    noticeDialogSummary.textContent = interimSummary
      || (body ? `${body.slice(0, 260)}${body.length > 260 ? "…" : ""}` : "상세 내용을 제공하지 않는 게시판입니다.");
    summaryNote.textContent = "현재는 본문에서 뽑은 임시 요약입니다.";
    if (body) {
      noticeDialogContent.textContent = body;
    } else {
      noticeDialogPlaceholder.hidden = false;
      noticeDialogPlaceholder.textContent = "이 게시판은 제목과 날짜만 공개하고 있습니다. 자세한 내용은 게시판 원문에서 확인해 주세요.";
    }

    try {
      const original = new URL(detail.original_url);
      if (["http:", "https:"].includes(original.protocol)) {
        noticeDialogOriginal.href = original.href;
        noticeDialogOriginal.hidden = false;
      }
    } catch {
      noticeDialogOriginal.hidden = true;
    }
  } catch {
    noticeDialogSummary.textContent = "상세 내용을 불러오지 못했습니다. 게시판 원문에서 확인해 주세요.";
  }
}

summaryButton?.addEventListener("click", async () => {
  if (!activeNoticeId) return;
  summaryButton.disabled = true;
  summaryButton.textContent = "AI 요약을 만드는 중…";
  try {
    const response = await fetch(`/api/assistant/notices/${encodeURIComponent(activeNoticeId)}/summary`, {
      method: "POST", credentials: "same-origin", headers: { Accept: "application/json" },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "AI 요약을 만들지 못했습니다.");
    noticeDialogSummary.textContent = data.summary;
    summaryNote.textContent = "공지 본문을 바탕으로 만든 AI 요약입니다.";
  } catch (error) {
    summaryNote.textContent = error.message || "AI 요약을 만들지 못했습니다.";
  } finally {
    summaryButton.disabled = false;
    summaryButton.textContent = "AI 요약 다시 만들기";
  }
});

function appendChatMessage(text, kind = "assistant") {
  const bubble = document.createElement("p");
  bubble.className = `chat-bubble ${kind === "user" ? "user-bubble" : "assistant-bubble"}`;
  bubble.textContent = text;
  chatMessages.append(bubble);
  bubble.scrollIntoView({ block: "nearest" });
  return bubble;
}

document.querySelector("[data-assistant-open]")?.addEventListener("click", () => {
  assistantDialog?.showModal();
  assistantDialog?.querySelector("#assistant-question")?.focus();
});
assistantDialog?.querySelector("[data-assistant-close]")?.addEventListener("click", () => assistantDialog.close());
assistantDialog?.querySelector("[data-chat-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = event.currentTarget.elements.question;
  const question = input.value.trim();
  if (!question) return;
  appendChatMessage(question, "user");
  input.value = "";
  chatStatus.textContent = "관련 공지를 찾고 있습니다.";
  const pending = appendChatMessage("관련 공지를 찾고 있어요…");
  try {
    const response = await fetch("/api/assistant/chat", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) throw new Error("로그인 후 공지 도우미를 사용할 수 있습니다.");
    if (!response.ok) throw new Error(data.detail || "질문을 처리하지 못했습니다.");
    pending.textContent = data.answer;
    (data.notices || []).forEach((notice) => {
      const result = document.createElement("article");
      result.className = "chat-notice-result";
      const title = document.createElement("button");
      title.type = "button";
      title.textContent = notice.title;
      title.addEventListener("click", () => openNoticeDetail(notice));
      const meta = document.createElement("small");
      meta.textContent = `${notice.source_name || "공지"}${notice.posted_at ? ` · ${formatDate(notice.posted_at)}` : ""}`;
      result.append(title, meta);
      if (notice.preview) {
        const preview = document.createElement("p");
        preview.textContent = notice.preview;
        result.append(preview);
      }
      chatMessages.append(result);
    });
    chatStatus.textContent = data.ai_enabled
      ? "공지 내용을 근거로 답변했습니다."
      : data.no_matches
        ? "질문과 관련된 공지를 찾지 못했습니다."
      : data.ai_failed
        ? "AI 응답에 실패했습니다. API 키와 모델 설정을 확인해 주세요."
        : "공지 검색 결과입니다. AI API 키를 설정하면 답변을 받을 수 있습니다.";
  } catch (error) {
    pending.textContent = error.message || "잠시 후 다시 시도해 주세요.";
    chatStatus.textContent = "";
  }
});

function makeNoticeCard(item) {
  const card = document.createElement("article");
  card.className = "notice-card";

  const date = document.createElement("time");
  date.className = "notice-date";
  date.dateTime = item.posted_at || "";
  date.textContent = formatDate(item.posted_at);

  const content = document.createElement("div");
  content.className = "notice-content";

  const meta = document.createElement("div");
  meta.className = "notice-meta";

  const source = document.createElement("span");
  source.className = "source-label";
  source.textContent = item.source_name || "충북대학교";
  meta.append(source);

  const saveButton = document.createElement("button");
  saveButton.className = "save-notice-button";
  saveButton.type = "button";
  saveButton.setAttribute("aria-pressed", String(Boolean(item.is_saved)));
  saveButton.textContent = item.is_saved ? "저장됨" : "저장";
  saveButton.addEventListener("click", async () => {
    const wasSaved = Boolean(item.is_saved);
    saveButton.disabled = true;
    try {
      const response = await fetch(`/api/notices/${encodeURIComponent(item.id)}/saved`, {
        method: wasSaved ? "DELETE" : "PUT",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (response.status === 401) {
        document.querySelector("[data-auth-open]")?.click();
        statusNode.textContent = "저장하려면 로그인해 주세요.";
        return;
      }
      if (!response.ok) throw new Error("저장 상태를 변경하지 못했습니다.");
      item.is_saved = !wasSaved;
      saveButton.setAttribute("aria-pressed", String(item.is_saved));
      saveButton.textContent = item.is_saved ? "저장됨" : "저장";
      statusNode.textContent = item.is_saved ? "공지를 저장했습니다." : "저장을 해제했습니다.";
      if (activeView === "saved" && wasSaved) {
        const savedTab = tabs.find((tab) => tab.dataset.view === "saved");
        if (savedTab) await loadNotices(savedTab);
      }
    } catch (error) {
      statusNode.textContent = error.message || "저장 상태를 변경하지 못했습니다.";
    } finally {
      saveButton.disabled = false;
    }
  });
  meta.append(saveButton);

  if (item.category_name) {
    const category = document.createElement("span");
    category.className = "category-pill";
    category.textContent = item.category_name;
    meta.append(category);
  }

  if (Array.isArray(item.tags)) {
    item.tags.forEach((tagName) => {
      const tag = document.createElement("span");
      tag.className = "topic-tag";
      tag.textContent = tagName;
      meta.append(tag);
    });
  }

  const title = document.createElement("button");
  title.className = "notice-title";
  title.type = "button";
  title.textContent = item.title || "제목 없음";
  title.setAttribute("aria-label", `${title.textContent} 상세 보기`);
  title.addEventListener("click", () => openNoticeDetail(item));

  const summaryText = item.summary || item.preview || "";
  const summary = document.createElement("p");
  summary.className = "notice-summary";
  summary.textContent = summaryText;

  content.append(meta, title);
  if (summaryText) content.append(summary);

  if (Array.isArray(item.reasons) && item.reasons.length) {
    const reasons = document.createElement("ul");
    reasons.className = "recommendation-reasons";
    reasons.setAttribute("aria-label", "추천 이유");
    item.reasons.forEach((reason) => {
      const reasonItem = document.createElement("li");
      reasonItem.textContent = reason;
      reasons.append(reasonItem);
    });
    content.append(reasons);
  }

  card.append(date, content);
  return card;
}

noticeDialog?.querySelector("[data-notice-close]")?.addEventListener("click", () => noticeDialog.close());

function renderNotices() {
  const query = searchInput.value.trim().toLocaleLowerCase("ko-KR");
  const filtered = query
    ? notices.filter((item) =>
        `${item.title || ""} ${item.summary || item.preview || ""} ${item.source_name || ""}`
          .toLocaleLowerCase("ko-KR")
          .includes(query),
      )
    : notices;

  if (!filtered.length) {
    if (query) {
      showMessage(`‘${searchInput.value.trim()}’ 검색 결과가 없습니다.`);
    } else if (activeView === "recommended") {
      showMessage("표시할 맞춤 공지가 없습니다.", "empty-state", "관심 분야와 대상이 맞는 공지가 등록되면 여기에 표시됩니다.");
    } else if (activeView === "other_department") {
      showMessage("지원 가능한 다른 학과 공지가 없습니다.", "empty-state", "다른 학과 공지 중 내 학과나 학년에 해당하는 공지가 있으면 여기에 표시됩니다.");
    } else if (activeView === "saved") {
      showMessage("저장한 공지가 없습니다.", "empty-state", "관심 있는 공지의 저장 버튼을 눌러 여기에 모아보세요.");
    } else {
      showMessage("표시할 공지가 없습니다.", "empty-state", "연결된 게시판에서 공지를 불러오면 여기에 표시됩니다.");
    }
    return;
  }
  listNode.replaceChildren(...filtered.map(makeNoticeCard));
}

async function loadNotices(tab) {
  activeView = tab.dataset.view;
  requestController?.abort();
  requestController = new AbortController();
  listNode.setAttribute("aria-busy", "true");
  showMessage("공지를 불러오는 중입니다.", "loading-state");
  const viewNames = {
    all: "전체",
    school: "학교",
    department: "내 학과",
    other_department: "지원 가능한 다른 학과",
    recommended: "맞춤",
    saved: "저장한",
  };
  statusNode.textContent = `${viewNames[activeView] || "전체"} 공지를 불러오는 중입니다.`;

  try {
    const response = await fetch(tab.dataset.endpoint, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
      signal: requestController.signal,
    });
    if (response.status === 401) {
      notices = [];
      statusNode.textContent = "로그인 후 확인할 수 있습니다.";
      showLoginRequired();
      return;
    }
    if (!response.ok) throw new Error("notice_request_failed");

    const data = await response.json();
    notices = Array.isArray(data.items) ? data.items : [];
    const total = Number.isFinite(Number(data.total)) ? Number(data.total) : notices.length;
    statusNode.textContent = `총 ${total}건`;
    renderNotices();
  } catch (error) {
    if (error.name === "AbortError") return;
    notices = [];
    statusNode.textContent = "공지 목록을 불러오지 못했습니다.";
    showMessage("잠시 후 다시 시도해 주세요.", "error");
  } finally {
    listNode.removeAttribute("aria-busy");
  }
}

function selectTab(tab) {
  tabs.forEach((other) => {
    const active = other === tab;
    other.classList.toggle("active", active);
    other.setAttribute("aria-selected", String(active));
    other.tabIndex = active ? 0 : -1;
  });
  listNode.setAttribute("aria-labelledby", tab.id);
  loadNotices(tab);
}

document.querySelectorAll("[data-view-link]").forEach((link) => {
  link.addEventListener("click", (event) => {
    const tab = tabs.find((item) => item.dataset.view === link.dataset.viewLink);
    if (window.location.pathname === "/") {
      event.preventDefault();
      if (tab) {
        selectTab(tab);
      } else {
        return;
      }
      document.querySelector("#notice-feed")?.scrollIntoView({ behavior: "smooth" });
    }
    document.querySelectorAll(".site-nav a").forEach((navLink) => navLink.classList.remove("nav-home"));
    if (link.closest(".site-nav")) link.classList.add("nav-home");
    menuToggle?.setAttribute("aria-expanded", "false");
    menuToggle?.setAttribute("aria-label", "메뉴 열기");
    mobileMenu?.setAttribute("hidden", "");
  });
});

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[nextIndex].focus();
    selectTab(tabs[nextIndex]);
  });
});

searchInput.addEventListener("input", renderNotices);
// Load the tab marked active in the page; the first tab is personalized,
// while the initial visual selection is the all notices tab.
loadNotices(tabs.find((tab) => tab.classList.contains("active")) || tabs[0]);
