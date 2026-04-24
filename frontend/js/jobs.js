const jobsContainer = document.getElementById("jobsContainer");

async function refreshJobs() {
  try {
    const jobs = await listJobs();
    jobsContainer.innerHTML = "";

    if (!jobs.length) {
      jobsContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-text">No jobs yet</div>
          <div class="empty-state-subtext">Upload an image to get started</div>
        </div>
      `;
      return;
    }

    jobs.forEach(job => {
      const row = document.createElement("div");
      row.className = "job-card";

      row.innerHTML = `
        <div class="job-info">
          <div class="job-header">
            <span class="job-id">Job #${job.display_id ?? job.job_id}</span>
            <span class="job-status status-${job.status}">${job.status.toUpperCase()}</span>
          </div>
          <div class="job-details">
            <div class="detail-item">
              <div class="detail-label">Created</div>
              <div class="detail-value">${new Date(job.created_at).toLocaleString()}</div>
            </div>
            <div class="detail-item">
              <div class="detail-label">Elapsed Time</div>
              <div class="detail-value">${job.metrics?.elapsed_ms ?? "-"} ms</div>
            </div>
            <div class="detail-item">
              <div class="detail-label">Blob Count</div>
              <div class="detail-value">${job.metrics?.blob_count ?? "-"}</div>
            </div>
          </div>
        </div>
        <div class="job-actions">
          ${job.status === "done" 
            ? `<button class="view-btn" onclick="viewResult('${job.job_id}')">View Result</button>` 
            : `<button class="view-btn" disabled>Processing...</button>`}
          <button class="secondary-btn" onclick="deleteJobAndRefresh('${job.job_id}')">Delete</button>
        </div>
      `;

      jobsContainer.appendChild(row);
    });
  } catch (error) {
    jobsContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-text">Sign in to view your jobs</div>
        <div class="empty-state-subtext">Your job list is protected by your login</div>
      </div>
    `;
  }
}

// Navigate to result page
function viewResult(jobId) {
  window.location.href = `result.html?job_id=${jobId}`;
}

async function deleteJobAndRefresh(jobId) {
  if (!confirm("Delete this job? This cannot be undone.")) {
    return;
  }
  try {
    await deleteJob(jobId);
    await refreshJobs();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

// Confirm and clear all history
async function confirmClearHistory() {
  if (!confirm("Warning: Are you sure you want to delete ALL job history? This cannot be undone.")) {
    return;
  }

  const clearBtn = document.querySelector(".danger-btn");
  clearBtn.disabled = true;
  clearBtn.textContent = "Clearing...";

  try {
    await clearAllHistory();
    jobsContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-text">History Cleared</div>
        <div class="empty-state-subtext">All jobs and images have been deleted</div>
      </div>
    `;
    clearBtn.textContent = "Clear All History";
    clearBtn.disabled = false;
  } catch (error) {
    alert(`Error: ${error.message}`);
    clearBtn.textContent = "Clear All History";
    clearBtn.disabled = false;
  }
}

// Refresh every second
setInterval(refreshJobs, 1000);
refreshJobs();

