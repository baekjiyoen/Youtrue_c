const urlParams = new URLSearchParams(window.location.search);
const video_id = urlParams.get('video_id');

const loadingImage = document.getElementById('loadingImage');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');

loadingImage.onload = function () {
  if (!video_id) {
    displayError("No video_id provided!");
    return;
  }

  // 작업 시작 요청
  setTimeout(() => {
    startJob(video_id)
      .then(data => {
        if (data.error) {
          displayError(`Error: ${data.error}`);
        } else {
          // 작업이 시작되었다고 가정하고, 진행률 폴링 시작
          pollProgress(video_id);
        }
      })
      .catch(err => {
        console.error(err);
        displayError("작업 시작 중 오류 발생");
      });
  }, 500);
};

// /prepare_data 호출
async function startJob(video_id) {
  const response = await fetch('/prepare_data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: video_id }),
  });
  
  if (!response.ok) {
    throw new Error("Server returned " + response.status + " " + response.statusText);
  }
  
  return response.json();
}


// 진행 상태 폴링
function pollProgress(job_id) {
  fetch('/progress?job_id=' + job_id)
    .then(res => res.json())
    .then(data => {
      const p = data.progress;
      updateProgressBar(p);

      if (data.finished) {
        // 완료 시 handleFinishedJob 호출
        setTimeout(() => handleFinishedJob(job_id), 2000);
      } else {
        // 아직 안 끝났으면 2초 후 다시 확인
        setTimeout(() => pollProgress(job_id), 2000);
      }
    })
    .catch(err => {
      console.error(err);
      displayError("작업 상태 확인 중 오류 발생");
    });
}

function updateProgressBar(progress) {
  progressBar.style.width = progress + '%';
  progressText.innerText = progress + '%';
}

function handleFinishedJob(video_id) {
  const form = createForm('/media', 'POST', {
    video_id: video_id
  });
  document.body.appendChild(form);

  const loadingContainer = document.getElementById('loadingContainer');
  if (loadingContainer) {
    loadingContainer.innerHTML = "";
  }

  addVideoToPage(videoSrc, form);
}

function displayError(message) {
  console.error(message);
  alert(message);
  document.body.innerHTML = `<p style="color: red; text-align: center;">${message}</p>`;
}

function createForm(action, method, inputs) {
  const form = document.createElement('form');
  form.action = action;
  form.method = method;

  Object.entries(inputs).forEach(([name, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
  });

  return form;
}

function addVideoToPage(videoSrc, form) {
  const video = document.createElement('video');
  video.src = videoSrc;
  video.setAttribute('autoplay', 'true');
  video.setAttribute('muted', 'true');
  video.setAttribute('playsinline', 'true');
  video.controls = false;

  video.style.position = "fixed";
  video.style.top = "0";
  video.style.left = "0";
  video.style.width = "100vw";
  video.style.height = "100vh";
  video.style.objectFit = "cover";
  video.style.zIndex = 99999;

  document.body.appendChild(video);

  // 영상 재생 완료 시 form 제출
  video.onended = function () {
    form.submit();
  };
}
