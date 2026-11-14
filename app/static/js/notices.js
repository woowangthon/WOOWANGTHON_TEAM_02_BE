const statusNode = document.querySelector("#feed-status");
const listNode = document.querySelector("#notice-list");
const searchInput = document.querySelector("#notice-search");
const tabs = [...document.querySelectorAll(".feed-tab")];

let activeView = "all";
let notices = [];
let requestController;

function showMessage(message, className = "empty-state") {
  const note = document.createElement("div");
  note.className = className;

  const text = document.createElement("p");
  text.textContent = message;
  note.append(text);
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
      : "내 학교의 공지 목록을 확인하려면 로그인해 주세요.";

  const link = document.createElement("a");
  link.className = "inline-login-link";
  link.href = "/login";
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

  if (item.category_name) {
    const category = document.createElement("span");
    category.className = "category-pill";
    category.textContent = item.category_name;
    meta.append(category);
  }

  const title = document.createElement("a");
  title.className = "notice-title";
  title.textContent = item.title || "제목 없음";
  try {
    const original = new URL(item.original_url);
    if (["http:", "https:"].includes(original.protocol)) {
      title.href = original.href;
      title.target = "_blank";
      title.rel = "noopener noreferrer";
    }
  } catch {
    title.removeAttribute("href");
  }

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
    showMessage(
      query
        ? `‘${searchInput.value.trim()}’ 검색 결과가 없습니다.`
        : activeView === "recommended"
          ? "현재 추천할 공지가 없습니다."
          : "아직 수집된 공지가 없습니다.",
    );
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
  statusNode.textContent = `${activeView === "recommended" ? "맞춤" : "전체"} 공지를 불러오는 중입니다.`;

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
loadNotices(tabs[0]);
