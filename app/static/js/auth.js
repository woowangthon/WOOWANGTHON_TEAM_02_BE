const guestState = document.querySelector("[data-auth-guest]");
const userState = document.querySelector("[data-auth-user]");
const emailNode = document.querySelector("[data-auth-email]");

function showGuest() {
  guestState?.removeAttribute("hidden");
  userState?.setAttribute("hidden", "");
  if (emailNode) emailNode.textContent = "";
}

function showUser(email) {
  guestState?.setAttribute("hidden", "");
  userState?.removeAttribute("hidden");
  if (emailNode) {
    emailNode.textContent = email || "로그인 계정";
    emailNode.title = email || "로그인 계정";
  }
}

async function resolveAuthState() {
  const serverEmail = document.body.dataset.userEmail;
  if (document.body.dataset.authenticated === "true") {
    showUser(serverEmail);
    return;
  }

  try {
    const response = await fetch("/me", {
      headers: { Accept: "text/html" },
      credentials: "same-origin",
      redirect: "manual",
    });
    if (!response.ok) {
      showGuest();
      return;
    }

    const html = await response.text();
    const profileDocument = new DOMParser().parseFromString(html, "text/html");
    const email = profileDocument.body.dataset.userEmail;
    if (profileDocument.body.dataset.authenticated === "true") {
      showUser(email);
    } else {
      showGuest();
    }
  } catch {
    showGuest();
  }
}

resolveAuthState();
