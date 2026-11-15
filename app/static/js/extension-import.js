(() => {
  const status = document.querySelector("#status");
  const preview = document.querySelector("#preview");
  const saveButton = document.querySelector("#save");
  let notice = null;

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    if (event.data?.source !== "cbnu-notice-extension" || event.data?.type !== "NOTICE_IMPORT_PREVIEW") return;
    notice = event.data.payload;
    if (!notice || !notice.title || !notice.content) {
      status.textContent = "공지 내용을 읽지 못했습니다. 공지 상세 페이지에서 다시 열어주세요.";
      return;
    }
    document.querySelector("#title").textContent = notice.title;
    document.querySelector("#meta").textContent = `${notice.department === "electrical" ? "전기공학부" : "컴퓨터공학과"} · ${notice.post_number}번 · ${notice.author || "작성자 정보 없음"} · ${notice.date}`;
    document.querySelector("#content").textContent = notice.content;
    const attachmentList = document.querySelector("#attachments");
    attachmentList.replaceChildren();
    for (const attachment of notice.attachments || []) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = attachment.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = attachment.name;
      item.append(link);
      attachmentList.append(item);
    }
    if (!notice.attachments?.length) attachmentList.textContent = "첨부파일이 없습니다.";
    preview.hidden = false;
    saveButton.hidden = false;
    status.textContent = "상세 내용입니다. 확인한 뒤 저장 버튼을 누르면 알려줌 DB에 추가됩니다.";
  });

  saveButton.addEventListener("click", async () => {
    if (!notice) return;
    saveButton.disabled = true;
    status.textContent = "공지 DB에 저장하고 있습니다...";
    try {
      const response = await fetch("/api/notices/manual-import", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(notice),
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) throw new Error("먼저 알려줌에 로그인한 뒤, 새 공지 확인을 다시 눌러주세요.");
      if (!response.ok) throw new Error(result.detail || `저장 실패 (${response.status})`);
      status.textContent = result.created ? "새 공지를 알려줌 DB에 저장했습니다." : "기존 공지 내용을 최신 내용으로 갱신했습니다.";
      saveButton.textContent = "저장 완료";
      window.postMessage({
        source: "cbnu-notice-extension",
        type: "NOTICE_IMPORT_SAVED",
        department: notice.department,
        post_number: notice.post_number,
      }, location.origin);
    } catch (error) {
      status.textContent = error.message || "저장하지 못했습니다.";
      saveButton.disabled = false;
    }
  });
})();
