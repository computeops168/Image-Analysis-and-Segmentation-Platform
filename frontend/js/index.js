const uploadBox = document.getElementById("uploadBox");
const imageInput = document.getElementById("imageInput");
const uploadBtn = document.getElementById("uploadBtn");
const statusBtn = document.getElementById("statusBtn");
const statusText = document.getElementById("statusText");
const previewWrapper = document.getElementById("previewWrapper");
const uploadContent = document.getElementById("uploadContent");
const previewImage = document.getElementById("previewImage");

let currentJobId = null;
let statusMode = "check";
const STORAGE_JOB_ID = "stem_last_job_id";
const STORAGE_MODE = "stem_mode";

// Open file picker
uploadBox.addEventListener("click", () => imageInput.click());

// Show preview
imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (!file) return;

  const previewUrl = URL.createObjectURL(file);
  previewImage.src = previewUrl;
  previewWrapper.classList.add("show");
  uploadContent.style.display = "none";
  uploadBox.classList.add("has-image");

  // New file selected: reset workflow to create a new job
  currentJobId = null;
  statusBtn.style.display = "none";
  setMode("check");
});

// Clear preview
function clearPreview() {
  imageInput.value = "";
  previewWrapper.classList.remove("show");
  uploadContent.style.display = "block";
  uploadBox.classList.remove("has-image");
  statusText.classList.remove("show");
  currentJobId = null;
  statusBtn.style.display = "none";
  setMode("check");
}

function setMode(nextMode) {
  statusMode = nextMode;
  if (statusMode === "check") {
    statusBtn.textContent = "Check Status";
  } else if (statusMode === "view") {
    statusBtn.textContent = "View Result";
  }
  saveState();
}

function saveState() {
  try {
    if (currentJobId) {
      localStorage.setItem(STORAGE_JOB_ID, currentJobId);
    } else {
      localStorage.removeItem(STORAGE_JOB_ID);
    }
    localStorage.setItem(STORAGE_MODE, statusMode);
  } catch (e) {
    // ignore storage errors
  }
}

function loadState() {
  try {
    const savedJobId = localStorage.getItem(STORAGE_JOB_ID);
    if (savedJobId) {
      currentJobId = savedJobId;
      statusBtn.style.display = "none";
      setMode("check");
      showStatus(`Last job #${currentJobId} is available in Jobs. You can start a new upload.`, "info");
    }
  } catch (e) {
    // ignore storage errors
  }
}

// Main button handler
uploadBtn.addEventListener("click", async () => {
  const file = imageInput.files[0];
  if (!file) {
    showStatus("Please select an image first", "error");
    return;
  }

  uploadBtn.disabled = true;
  uploadBtn.textContent = "Processing...";
  showStatus("Uploading image...", "info");

  try {
    const uploadResult = await uploadImage(file);

    showStatus("Creating job...", "info");
    const jobResult = await createJob(uploadResult.image_id);

    currentJobId = jobResult.job_id;
    showStatus(`Job #${currentJobId} created. Waiting for completion...`, "info");
    saveState();

    setMode("check");
    statusBtn.style.display = "inline-flex";
    uploadBtn.disabled = false;
  } catch (error) {
    uploadBtn.disabled = false;
    statusBtn.style.display = "none";
    showStatus(`Error: ${error.message}`, "error");
  }
});

statusBtn.addEventListener("click", async () => {
  if (!currentJobId) {
    showStatus("No job to check yet. Create a job first.", "error");
    return;
  }
  if (statusMode === "view") {
    window.location.href = `result.html?job_id=${currentJobId}`;
    return;
  }
  await checkJobStatus();
});

// Check job status when user clicks
async function checkJobStatus() {
  statusBtn.disabled = true;
  statusBtn.textContent = "Checking...";
  
  try {
    const job = await getJob(currentJobId);
    if (!job) {
      showStatus("Job not found", "error");
      setMode("check");
      statusBtn.disabled = false;
      statusBtn.textContent = "Check Status";
      return;
    }

    if (job.status === "done") {
      showStatus('Job complete. Click "View Result" to see the analysis.', "success");
      setMode("view");
      statusBtn.disabled = false;
    } else {
      showStatus('Job still processing. Click "Check Status" again to update.', "info");
      setMode("check");
      statusBtn.disabled = false;
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, "error");
    setMode("check");
    statusBtn.disabled = false;
  }
}

// Helper to show status messages
function showStatus(message, type) {
  statusText.textContent = message;
  statusText.classList.add("show");
  statusText.classList.remove("success", "error", "info");
  statusText.classList.add(type);
}

loadState();

