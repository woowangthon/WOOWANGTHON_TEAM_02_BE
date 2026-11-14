const authDialog = document.querySelector("#auth-dialog");
const authCloseButton = document.querySelector("[data-auth-close]");
const authTabs = [...document.querySelectorAll("[data-auth-tab]")];
const authPanels = [...document.querySelectorAll("[data-auth-panel]")];
const authFeedback = document.querySelector("[data-auth-feedback]");

function setAuthTab(name) {
  authTabs.forEach((tab) => {
    const active = tab.dataset.authTab === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  authPanels.forEach((panel) => {
    panel.hidden = panel.dataset.authPanel !== name;
  });
  document.querySelector("#auth-title").textContent =
    name === "login" ? "다시 만나서 반가워요." : "알려줌과 함께 시작해요.";
  document.querySelector(".dialog-description").textContent =
    name === "login"
      ? "로그인하면 학과와 관심 분야에 맞는 공지를 확인할 수 있습니다."
      : "학교와 학과를 등록하고 나에게 맞는 공지를 받아보세요.";
  authFeedback.hidden = true;
  authFeedback.textContent = "";
}

function showFeedback(message, isError = false) {
  authFeedback.hidden = !message;
  authFeedback.textContent = message;
  authFeedback.classList.toggle("is-error", isError);
}

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-auth-open]")) return;
  setAuthTab("login");
  authDialog?.showModal();
  document.querySelector("#modal-email")?.focus();
});

authCloseButton?.addEventListener("click", () => authDialog?.close());
authDialog?.addEventListener("click", (event) => {
  if (event.target === authDialog) authDialog.close();
});

authTabs.forEach((tab) => {
  tab.addEventListener("click", () => setAuthTab(tab.dataset.authTab));
});

const schoolSelect = document.querySelector("#modal-school");
const departmentSelect = document.querySelector("#modal-department");

if (schoolSelect && departmentSelect) {
  function filterDepartments() {
    const schoolId = schoolSelect.value;
    departmentSelect.querySelectorAll("optgroup[data-school-id]").forEach((group) => {
      group.disabled = group.dataset.schoolId !== schoolId;
    });
    departmentSelect.disabled = !schoolId;
    const selectedGroup = departmentSelect.selectedOptions[0]?.parentElement;
    if (departmentSelect.value && selectedGroup?.dataset.schoolId !== schoolId) {
      departmentSelect.value = "";
    }
  }

  schoolSelect.addEventListener("change", () => {
    departmentSelect.value = "";
    filterDepartments();
  });
  filterDepartments();
}

document.querySelectorAll("[data-modal-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("[type=submit]");
    submitButton.disabled = true;
    showFeedback(form.dataset.modalForm === "login" ? "로그인 중입니다." : "가입 정보를 확인하고 있습니다.");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { Accept: "text/html" },
      });
      const html = await response.text();
      const documentResult = new DOMParser().parseFromString(html, "text/html");

      if (form.dataset.modalForm === "login") {
        const profileEmail = documentResult.body.dataset.userEmail;
        if (response.ok && documentResult.body.dataset.authenticated === "true") {
          document.querySelector("[data-auth-guest]")?.setAttribute("hidden", "");
          const userNav = document.querySelector("[data-auth-user]");
          userNav?.removeAttribute("hidden");
          const emailNode = document.querySelector("[data-auth-email]");
          if (emailNode) emailNode.textContent = profileEmail || "내 정보";
          authDialog.close();
          return;
        }
      } else {
        const successMessage = documentResult.querySelector(".notice")?.textContent.trim();
        if (response.ok && successMessage) {
          const email = form.querySelector('[name="email"]')?.value || "";
          setAuthTab("login");
          document.querySelector("#modal-email").value = email;
          showFeedback(successMessage);
          return;
        }
      }

      const errorMessage = documentResult.querySelector("[role=alert], .error")?.textContent.trim();
      showFeedback(errorMessage || "요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요.", true);
    } catch {
      showFeedback("서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.", true);
    } finally {
      submitButton.disabled = false;
    }
  });
});
