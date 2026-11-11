const statusNode = document.querySelector("#feed-status");
const listNode = document.querySelector("#notice-list");

function showMessage(message, className = "empty-state") {
  const note = document.createElement("p");
  note.className = className;
  note.textContent = message;
  listNode.replaceChildren(note);
}

function makeNoticeCard(item) {
  const card = document.createElement("article");
  card.className = "notice-card";

  const meta = document.createElement("div");
  meta.className = "notice-meta";

  const source = document.createElement("span");
  source.className = "source-label";
  source.textContent = item.source_name || "충북대학교";

  const category = document.createElement("span");
  category.className = "category-pill";
  category.textContent = item.category_name || "전체 공지";

  const date = document.createElement("time");
  date.dateTime = item.posted_at || "";
  date.textContent = item.posted_at
    ? new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium" }).format(new Date(item.posted_at))
    : "게시일 미상";
  meta.append(source, category, date);

  const link = document.createElement("a");
  link.className = "notice-title";
  link.textContent = item.title;
  try {
    const original = new URL(item.original_url);
    if (["http:", "https:"].includes(original.protocol)) {
      link.href = original.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
  } catch {
    link.removeAttribute("href");
  }

  const summary = document.createElement("p");
  summary.className = "notice-summary";
  summary.textContent = item.summary || "본문 요약이 아직 준비되지 않았습니다.";

  card.append(meta, link, summary);
  return card;
}

async function loadNotices(scope) {
  listNode.replaceChildren();
  statusNode.textContent = `${scope === "school" ? "학교" : "학과·학부"} 공지를 불러오는 중…`;

  try {
    const response = await fetch(`/api/notices?per_page=20&scope=${scope}`, {
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      statusNode.textContent = "로그인하면 충북대 공지를 볼 수 있어요.";
      showMessage("공지 목록을 보려면 먼저 로그인해 주세요.");
      return;
    }
    if (!response.ok) throw new Error("공지 목록을 불러오지 못했습니다.");

    const data = await response.json();
    statusNode.textContent = `총 ${data.total}건 · 최신순`;
    if (data.items.length === 0) {
      showMessage(scope === "school"
        ? "아직 수집된 학교 공지가 없습니다. 잠시 후 다시 확인해 주세요."
        : "등록된 학과·학부 공지가 없습니다.");
      return;
    }
    listNode.replaceChildren(...data.items.map(makeNoticeCard));
  } catch {
    statusNode.textContent = "공지 목록을 불러오지 못했어요.";
    showMessage("잠시 후 새로고침해 주세요.", "error");
  }
}

document.querySelectorAll(".feed-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".feed-tab").forEach((other) => {
      const active = other === tab;
      other.classList.toggle("active", active);
      other.setAttribute("aria-selected", String(active));
    });
    loadNotices(tab.dataset.scope);
  });
});

loadNotices("school");
