const resultContent = document.getElementById("resultContent");

// Get job_id from URL
const params = new URLSearchParams(window.location.search);
const jobId = params.get("job_id");

async function showResult() {
  if (!jobId) {
    resultContent.innerHTML = `<div class="error-message">Error: Job ID not found in URL.</div>`;
    return;
  }

  const job = await getJob(jobId);
  if (!job) {
    resultContent.innerHTML = `<div class="error-message">Error: Job not found.</div>`;
    return;
  }

  const createdDate = new Date(job.created_at).toLocaleString();
  const metrics = job.metrics || {};
  const outputUrl = job.output_url || job.outputUrl || job.image_url || "";
  const statusText = (job.status || "").toUpperCase();
  
  let imageMarkup = `<div class="error-message">No output image available.</div>`;
  if (outputUrl) {
    try {
      const authHeaders = typeof buildAnyAuthHeaders === "function"
        ? buildAnyAuthHeaders()
        : (typeof buildAuthHeaders === "function" ? buildAuthHeaders() : {});
      const res = await fetch(outputUrl, { headers: authHeaders });
      if (res.status === 401 || res.status === 403) {
        imageMarkup = `<div class="error-message">Sign in to view this result.</div>`;
      } else if (!res.ok) {
        throw new Error(`Image request failed: ${res.status}`);
      } else {
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        imageMarkup = `<img class="result" src="${objectUrl}" alt="Output Image">`;
      }
    } catch (err) {
      imageMarkup = `<div class="error-message">Could not load output image.</div>`;
    }
  }

  resultContent.innerHTML = `
    <div class="result-layout">
      <div class="result-image-section">
        <div class="result-image-container">
          ${imageMarkup}
        </div>
        <div class="image-caption">Processed output image</div>
      </div>
      
      <div class="result-info-section">
        <div class="job-metadata">
          <div class="metadata-row">
            <span class="metadata-label">Job ID</span>
            <span class="metadata-value">#${job.job_id}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Status</span>
            <span class="status-badge status-${job.status}">${statusText}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Created</span>
            <span class="metadata-value">${createdDate}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Elapsed Time</span>
            <span class="metadata-value">${metrics.elapsed_ms ?? "-"} ms</span>
          </div>
        </div>
        
        <div class="metrics-section">
          <div class="metrics-title">Metrics</div>
          <div class="metrics-grid">
            <div class="metric-item">
              <div class="metric-label">Blob Count</div>
              <div class="metric-value">${metrics.blob_count ?? "-"}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">Processing</div>
              <div class="metric-value">${job.status === "done" ? "Complete" : "In Progress"}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">Status</div>
              <div class="metric-value metric-success">${statusText || "UNKNOWN"}</div>
            </div>
          </div>
        </div>
        
        <div class="action-buttons">
          <button class="secondary-btn" onclick="window.location.href='jobs.html'">Back to Jobs</button>
          <button class="secondary-btn" onclick="window.location.href='index.html'">Upload New</button>
        </div>
      </div>
    </div>
  `;
}

// Show immediately
showResult();

