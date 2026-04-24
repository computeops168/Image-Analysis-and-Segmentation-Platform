const userLoginCard = document.getElementById("userLoginCard");

if (userLoginCard) {
  const userUsername = document.getElementById("userUsername");
  const userPassword = document.getElementById("userPassword");
  const userLoginBtn = document.getElementById("userLoginBtn");
  const userLogoutBtn = document.getElementById("userLogoutBtn");
  const userAuthMsg = document.getElementById("userAuthMsg");

  const USER_NAME_KEY = "stem_user_name";

  function getStoredUsername() {
    try {
      return localStorage.getItem(USER_NAME_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  function setStoredUsername(name) {
    try {
      if (name) {
        localStorage.setItem(USER_NAME_KEY, name);
      } else {
        localStorage.removeItem(USER_NAME_KEY);
      }
    } catch (e) {
      // ignore
    }
  }

  function showLoggedIn(name) {
    userLoginBtn.style.display = "none";
    userLogoutBtn.style.display = "inline-flex";
    userPassword.value = "";
    userAuthMsg.textContent = name ? `Signed in as ${name}` : "Signed in";
  }

  function showLoggedOut() {
    userLoginBtn.style.display = "inline-flex";
    userLogoutBtn.style.display = "none";
    userAuthMsg.textContent = "Sign in to view your uploads and jobs";
  }

  async function handleLogin() {
    const username = (userUsername.value || "").trim();
    const password = userPassword.value || "";
    if (!username || !password) {
      userAuthMsg.textContent = "Enter your username and password";
      return;
    }
    userLoginBtn.disabled = true;
    userLoginBtn.textContent = "Signing in...";
    try {
      const data = await userLogin(username, password);
      setStoredUsername(data.username || username);
      showLoggedIn(data.username || username);
      if (typeof refreshJobs === "function") {
        refreshJobs();
      }
    } catch (error) {
      userAuthMsg.textContent = error.message || "Login failed";
    } finally {
      userLoginBtn.disabled = false;
      userLoginBtn.textContent = "Sign in";
    }
  }

  function handleLogout() {
    userLogout();
    setStoredUsername("");
    showLoggedOut();
    if (typeof refreshJobs === "function") {
      refreshJobs();
    }
  }

  userLoginBtn.addEventListener("click", handleLogin);
  userLogoutBtn.addEventListener("click", handleLogout);
  userPassword.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      handleLogin();
    }
  });

  if (getUserToken()) {
    showLoggedIn(getStoredUsername());
  } else {
    showLoggedOut();
  }
}
