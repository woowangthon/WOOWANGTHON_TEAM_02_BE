const summary = document.querySelector("#summary");
const meta = document.querySelector("#meta");
const list = document.querySelector("#notices");

function render(result) {
  if (!result) return;
  list.replaceChildren();
  if (result.status === "checking") {
    summary.textContent = `${departmentName(result.department)} 홈페이지를 확인하고 있습니다...`;
    meta.textContent = "공지 목록을 읽고 DB와 비교합니다.";
    return;
  }
  if (result.status === "error") {
    summary.textContent = "확인하지 못했습니다.";
    meta.textContent = result.error || "오류 내용을 확인할 수 없습니다.";
    return;
  }
  if (result.status !== "done") return;

  const newNotices = result.newNotices || [];
  const saved = result.savedNotice;
  const remaining = saved
    ? newNotices.filter((item) => !(item.department === saved.department && item.post_number === saved.post_number))
    : newNotices;
  const newCount = newNotices.filter((item) => !item.update_existing).length;
  const updateCount = newNotices.length - newCount;
  summary.textContent = saved
    ? `${departmentName(saved.department)} ${saved.post_number}번 공지의 ${saved.update_existing ? "상세 내용을 갱신했습니다." : "상세 내용을 저장했습니다."}`
    : newCount || updateCount
      ? [`새 공지 ${newCount}건`, `저장된 공지 ${updateCount}건(최신 내용 확인 가능)`].filter((label, index) => index === 0 ? newCount > 0 : updateCount > 0).join(" · ") + "을 찾았습니다."
      : "새 공지나 본문 보완 대상이 없습니다.";
  meta.textContent = `${departmentName(result.department)} · 목록 ${result.listCount}건 확인 · ${new Date(result.checkedAt).toLocaleString("ko-KR")}`;

  for (const notice of remaining) {
    const item = document.createElement("li");
    item.className = "notice";
    const text = document.createElement("div");
    const title = document.createElement("p");
    title.className = "notice-title";
    title.textContent = notice.title;
    const details = document.createElement("p");
    details.className = "notice-meta";
    details.textContent = `게시글 ${notice.post_number}${notice.date ? ` · ${notice.date}` : ""}`;
    const link = document.createElement("a");
    link.href = notice.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = notice.update_existing
      ? notice.content_length > 0 ? "최신 내용으로 갱신 →" : "본문 보완하기 →"
      : "상세 확인 및 저장 →";
    text.append(title, details);
    item.append(text, link);
    list.append(item);
  }
}

function departmentName(value) {
  return value === "electrical" ? "전기공학부" : "컴퓨터공학과";
}

chrome.storage.local.get("lastCheck").then(({ lastCheck }) => render(lastCheck));
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.lastCheck) render(changes.lastCheck.newValue);
});
