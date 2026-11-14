const statusNode = document.querySelector("#feed-status");
const listNode = document.querySelector("#notice-list");
const searchInput = document.querySelector("#notice-search");
const tabs = [...document.querySelectorAll(".feed-tab")];
const todayDate = document.querySelector("#today-date");
const menuToggle = document.querySelector("[data-menu-toggle]");
const mobileMenu = document.querySelector("[data-mobile-menu]");

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
    if (query) {
      showMessage(`‘${searchInput.value.trim()}’ 검색 결과가 없습니다.`);
    } else if (activeView === "recommended") {
      showMessage("표시할 맞춤 공지가 없습니다.", "empty-state", "관심 분야와 대상이 맞는 공지가 등록되면 여기에 표시됩니다.");
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
    department: "학과",
    recommended: "맞춤",
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
      } else if (link.dataset.viewLink === "saved") {
        requestController?.abort();
        activeView = "saved";
        tabs.forEach((item) => {
          item.classList.remove("active");
          item.setAttribute("aria-selected", "false");
          item.tabIndex = -1;
        });
        statusNode.textContent = "저장한 공지";
        showMessage("저장한 공지가 없습니다.", "empty-state", "공지 저장 기능은 준비 중입니다.");
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
loadNotices(tabs[0]);
