const loginCard = document.getElementById("loginCard");
const adminCard = document.getElementById("adminCard");
const statTotal = document.getElementById("statTotal");
const statSuccess = document.getElementById("statSuccess");
const statElapsed = document.getElementById("statElapsed");
const statBlobs = document.getElementById("statBlobs");
const statusList = document.getElementById("statusList");
const recentList = document.getElementById("recentList");
const lastUpdated = document.getElementById("lastUpdated");
const adminUsername = document.getElementById("adminUsername");
const adminPassword = document.getElementById("adminPassword");
const loginBtn = document.getElementById("loginBtn");
const logoutBtn = document.getElementById("logoutBtn");
const authMsg = document.getElementById("authMsg");
const userList = document.getElementById("userList");
const newUsername = document.getElementById("newUsername");
const newPassword = document.getElementById("newPassword");
const newIsAdmin = document.getElementById("newIsAdmin");
const createUserBtn = document.getElementById("createUserBtn");
const userFormMsg = document.getElementById("userFormMsg");

let isAuthValid = false;

function hasToken() {
  try {
    return !!localStorage.getItem("stem_admin_token");
  } catch (e) {
    return false;
  }
}

function setAuthMessage(message, ok) {
  authMsg.textContent = message;
  authMsg.style.color = ok ? "#166534" : "#6b7280";
}

function showLoginView(message) {
  loginCard.style.display = "block";
  adminCard.style.display = "none";
  if (message) {
    setAuthMessage(message, false);
  }
}

function showAdminView() {
  loginCard.style.display = "none";
  adminCard.style.display = "block";
}

function clearAdminDisplay() {
  statTotal.textContent = "0";
  statSuccess.textContent = "0%";
  statElapsed.textContent = "0 ms";
  statBlobs.textContent = "0";
  statusList.innerHTML = `<div class="empty-state">No jobs yet</div>`;
  recentList.innerHTML = `<div class="empty-state">No recent jobs</div>`;
  if (userList) {
    userList.innerHTML = `<div class="empty-state">No users yet</div>`;
  }
  lastUpdated.textContent = "Login required";
}

function formatNumber(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString();
}

function statusOrder(keys) {
  const preferred = ["done", "pending", "failed", "error"];
  const remaining = keys.filter(k => !preferred.includes(k)).sort();
  return preferred.filter(k => keys.includes(k)).concat(remaining);
}

function renderStatusBreakdown(byStatus, total) {
  statusList.innerHTML = "";
  if (!total) {
    statusList.innerHTML = `<div class="empty-state">No jobs yet</div>`;
    return;
  }

  const keys = statusOrder(Object.keys(byStatus || {}));
  keys.forEach(status => {
    const count = byStatus[status] || 0;
    const percent = total ? Math.round((count / total) * 100) : 0;

    const row = document.createElement("div");
    row.className = "status-row";
    row.innerHTML = `
      <div class="status-pill status-${status}">${status.toUpperCase()}</div>
      <div class="status-bar"><span style="width: ${percent}%"></span></div>
      <div>${percent}%</div>
    `;
    statusList.appendChild(row);
  });
}

function renderRecent(recent) {
  recentList.innerHTML = "";
  if (!recent || !recent.length) {
    recentList.innerHTML = `<div class="empty-state">No recent jobs</div>`;
    return;
  }

  recent.forEach(job => {
    const metrics = job.metrics || {};
    const row = document.createElement("div");
    row.className = "recent-item";
    row.innerHTML = `
      <div>
        <div class="recent-title">Job #${job.display_id ?? job.job_id}</div>
        <div class="recent-meta">
          <div>Status: <span class="status-pill status-${job.status}">${String(job.status || "").toUpperCase()}</span></div>
          <div>Created: ${job.created_at || "-"}</div>
          <div>Elapsed: ${metrics.elapsed_ms ?? "-"} ms | Blobs: ${metrics.blob_count ?? "-"}</div>
        </div>
      </div>
      <div>
        ${job.status === "done"
          ? `<button class="view-btn" onclick="viewResult('${job.job_id}')">View</button>`
          : `<button class="view-btn" disabled>Processing...</button>`}
      </div>
    `;
    recentList.appendChild(row);
  });
}

function updateStatsDisplay(stats) {
  statTotal.textContent = formatNumber(stats.total);
  statSuccess.textContent = `${formatNumber(stats.success_rate)}%`;
  statElapsed.textContent = `${formatNumber(stats.avg_elapsed_ms)} ms`;
  statBlobs.textContent = formatNumber(stats.avg_blob_count);
  renderStatusBreakdown(stats.by_status || {}, stats.total || 0);
  renderRecent(stats.recent || []);
}

function renderUsers(users) {
  if (!userList) return;
  userList.innerHTML = "";
  if (!users || !users.length) {
    userList.innerHTML = `<div class="empty-state">No users yet</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "user-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Username</th>
        <th>Role</th>
        <th>Images</th>
        <th>Jobs</th>
        <th>Created</th>
        <th></th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  users.forEach(user => {
    const row = document.createElement("tr");
    const roleLabel = user.is_admin ? "Admin" : "User";
    const created = user.created_at ? new Date(user.created_at).toLocaleString() : "-";
    row.innerHTML = `
      <td>${user.username}</td>
      <td>${user.is_admin ? `<span class="user-pill">${roleLabel}</span>` : roleLabel}</td>
      <td>${user.image_count ?? 0}</td>
      <td>${user.job_count ?? 0}</td>
      <td>${created}</td>
      <td class="user-actions">
        <button class="mini-btn danger" data-user-id="${user.user_id}" ${user.is_admin ? "disabled" : ""}>Delete</button>
      </td>
    `;
    tbody.appendChild(row);
  });
  userList.appendChild(table);

  userList.querySelectorAll("button[data-user-id]").forEach(btn => {
    btn.addEventListener("click", async (event) => {
      const userId = event.currentTarget.getAttribute("data-user-id");
      await handleDeleteUser(userId);
    });
  });
}

async function refreshAdminStats() {
  if (!hasToken()) {
    isAuthValid = false;
    showLoginView("Sign in to access admin analytics");
    clearAdminDisplay();
    return;
  }
  try {
    const [stats, users] = await Promise.all([getAdminStats(), adminListUsers()]);
    isAuthValid = true;
    showAdminView();
    updateStatsDisplay(stats);
    renderUsers(users);
    lastUpdated.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    if (String(error.message || "").includes("Unauthorized")) {
      isAuthValid = false;
      adminLogout();
      showLoginView("Session expired. Please log in again.");
      clearAdminDisplay();
      return;
    }
    lastUpdated.textContent = "Error loading stats";
  }
}

function viewResult(jobId) {
  window.location.href = `result.html?job_id=${jobId}`;
}

async function confirmClearHistory() {
  if (!hasToken() || !isAuthValid) {
    alert("Admin login required");
    return;
  }

  if (!confirm("Warning: Are you sure you want to delete ALL job history? This cannot be undone.")) {
    return;
  }

  const clearBtn = document.getElementById("clearBtn");
  clearBtn.disabled = true;
  clearBtn.textContent = "Clearing...";

  try {
    await clearAllHistory();
    clearBtn.textContent = "Clear All History";
    clearBtn.disabled = false;
    refreshAdminStats();
  } catch (error) {
    alert(`Error: ${error.message}`);
    clearBtn.textContent = "Clear All History";
    clearBtn.disabled = false;
  }
}

async function handleLogin() {
  const username = (adminUsername.value || "").trim();
  const password = adminPassword.value || "";
  if (!username || !password) {
    setAuthMessage("Enter username and password", false);
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = "Signing in...";
  try {
    await adminLogin(username, password);
    isAuthValid = true;
    adminPassword.value = "";
    setAuthMessage("Authenticated", true);
    await refreshAdminStats();
  } catch (error) {
    setAuthMessage(String(error.message || "Login failed"), false);
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = "Login";
  }
}

function handleLogout() {
  adminLogout();
  isAuthValid = false;
  adminUsername.value = "";
  adminPassword.value = "";
  if (newUsername) newUsername.value = "";
  if (newPassword) newPassword.value = "";
  if (newIsAdmin) newIsAdmin.checked = false;
  showLoginView("You have been logged out.");
  clearAdminDisplay();
}

async function handleCreateUser() {
  if (!hasToken() || !isAuthValid) {
    userFormMsg.textContent = "Admin login required";
    return;
  }
  const username = (newUsername.value || "").trim();
  const password = newPassword.value || "";
  if (!username || !password) {
    userFormMsg.textContent = "Enter a username and password";
    return;
  }
  createUserBtn.disabled = true;
  createUserBtn.textContent = "Creating...";
  try {
    await adminRegisterUser(username, password, newIsAdmin.checked);
    userFormMsg.textContent = `Created user ${username}`;
    newPassword.value = "";
    await refreshAdminStats();
  } catch (error) {
    userFormMsg.textContent = String(error.message || "Failed to create user");
  } finally {
    createUserBtn.disabled = false;
    createUserBtn.textContent = "Create User";
  }
}

async function handleDeleteUser(userId) {
  if (!hasToken() || !isAuthValid) {
    alert("Admin login required");
    return;
  }
  if (!confirm("Delete this user and all their jobs/uploads? This cannot be undone.")) {
    return;
  }
  try {
    await adminDeleteUser(userId);
    await refreshAdminStats();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

loginBtn.addEventListener("click", handleLogin);
logoutBtn.addEventListener("click", handleLogout);
if (createUserBtn) {
  createUserBtn.addEventListener("click", handleCreateUser);
}
adminPassword.addEventListener("keydown", (event) => {
  if (event.key === "Enter") handleLogin();
});

setInterval(() => {
  if (adminCard.style.display !== "none") {
    refreshAdminStats();
  }
}, 2000);

if (hasToken()) {
  refreshAdminStats();
} else {
  showLoginView("Sign in to access admin analytics");
  clearAdminDisplay();
}
