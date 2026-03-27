let emotionChart = null;
let videoChart = null;

async function uploadVideo() {
  const fileInput = document.getElementById("videoInput");
  const preview = document.getElementById("preview");
  const video = document.getElementById("videoPreview");
  const loader = document.getElementById("loader");
  const verdictBadge = document.getElementById("verdictBadge");
  const reasonsList = document.getElementById("reasonsList");
  const transcriptBox = document.getElementById("transcriptBox");
  const emotionCanvas = document.getElementById("emotionChart");
  const videoCanvas = document.getElementById("videoChart");
  const kpiFaces = document.getElementById("kpiFaces");
  const kpiGaze = document.getElementById("kpiGaze");
  const kpiSpeech = document.getElementById("kpiSpeech");

  if (!fileInput.files.length) {
    alert("Please select a video first!");
    return;
  }

  // 🎞️ Show video preview
  const file = fileInput.files[0];
  video.src = URL.createObjectURL(file);
  preview.style.display = "block";

  // Prepare upload
  const formData = new FormData();
  formData.append("video", file);
  loader.style.display = "block";
  transcriptBox.textContent = "";
  reasonsList.innerHTML = "";
  verdictBadge.className = "badge bg-secondary";
  verdictBadge.textContent = "Analyzing...";
  if (emotionChart) emotionChart.destroy();
  if (videoChart) videoChart.destroy();

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
        const errorBody = await response.text();
        console.error("SERVER ERROR HTML DETECTED (UPLOAD):", errorBody);
        throw new Error(`Upload Failed (${response.status})`);
    }

    const data = await response.json();
    loader.style.display = "none";

    if (data.status === "success") {
      const a = data.analysis;
      const v = a.video || {};
      const au = a.audio || {};
      const cls = a.classification || {};

      // Verdict
      verdictBadge.textContent = cls.verdict || "Unknown";
      verdictBadge.className = cls.verdict === "Suspicious" ? "badge bg-danger" : "badge bg-success";
      (cls.reasons || []).forEach(r => {
        const li = document.createElement('li');
        li.textContent = r;
        reasonsList.appendChild(li);
      });

      // KPIs
      const sampled = v.sampledFrames || 1;
      const pct = (n) => `${Math.round((n / sampled) * 100)}%`;
      kpiFaces.textContent = pct(v.multiFaceFrames || 0);
      kpiGaze.textContent = pct(v.gazeAwayFrames || 0);
      kpiSpeech.textContent = `${Math.round((au.speechRatio || 0) * 100)}%`;

      // Transcript
      transcriptBox.textContent = a.transcript || "";

      // Emotion chart
      const emotions = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]; // DeepFace classes
      const emotionData = emotions.map((e) => (e === (a.emotion || '').toLowerCase() ? 90 : 10));
      emotionChart = new Chart(emotionCanvas, {
        type: "bar",
        data: {
          labels: emotions,
          datasets: [
            {
              label: "Emotion Intensity",
              data: emotionData,
              backgroundColor: "rgba(0, 204, 255, 0.6)",
            },
          ],
        },
        options: { scales: { y: { beginAtZero: true, max: 100 } } },
      });

      // Video activity chart
      const videoLabels = ["Multi-face", "No-face", "Identity mismatch", "Gaze away", "Head pose out"];
      const videoData = [v.multiFaceFrames, v.noFaceFrames, v.identityMismatchFrames, v.gazeAwayFrames, v.headPoseOutFrames].map(x => x || 0);
      videoChart = new Chart(videoCanvas, {
        type: "radar",
        data: {
          labels: videoLabels,
          datasets: [
            {
              label: "Frame counts",
              data: videoData,
              backgroundColor: "rgba(255, 99, 132, 0.2)",
              borderColor: "rgba(255, 99, 132, 1)",
            }
          ]
        },
        options: { scales: { r: { beginAtZero: true } } }
      });
    } else {
      verdictBadge.textContent = "Error";
      verdictBadge.className = "badge bg-danger";
      const msg = data.message || (data.analysis && data.analysis.error) || "Unknown error";
      const li = document.createElement('li');
      li.textContent = msg;
      reasonsList.appendChild(li);
    }
  } catch (err) {
    loader.style.display = "none";
    verdictBadge.textContent = "Network error";
    verdictBadge.className = "badge bg-danger";
    const li = document.createElement('li');
    li.textContent = err.message;
    reasonsList.appendChild(li);
  }
}
