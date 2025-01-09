const { createApp } = Vue;

let appInstance = null;

const socket = io.connect(window.location.origin);

window.onpopstate = function(event) {
  // 뒤로가기 이벤트 감지 시 메인 페이지로 이동
  window.location.href = '/index';
};

socket.on('connect', () => {
  console.log("socket connected");
});

appInstance = createApp({
  data() {
    return {
      video_id: video_id,
      summary: summary,
      script: script,
      player: null,
      pin: '',
      currentPin: pin,
      showQRCode: false
    };
  },
  computed: {
    renderedScript() {
      return this.script.map(line => line.replace(/\n/g, '<br>'));
    },
    scriptAsText() {
      if (Array.isArray(this.script)) {
        this.subtitle_list = this.script;
        return this.subtitle_list;
      }
      return [];
    }
  },
  created() {
    socket.on('message', (msg) => {
      // console.log('Server Message:', msg);
    });

    // 여기서 control 페이지로부터의 command 이벤트를 수신하고 처리
    socket.on('command', (data) => {
      const command = data.command;
      const value = data.value || 0;
      console.log('Received command:', command, 'value:', value);
      if (this.player) {
        switch(command) {
          case 'play':
            this.player.playVideo();
            break;
          case 'pause':
            this.player.pauseVideo();
            break;
          case 'stop':
            this.player.stopVideo();
            break;
          case 'forward':
            const currentForwardTime = this.player.getCurrentTime();
            this.player.seekTo(currentForwardTime + value, true);
            break;
          case 'backward':
            const currentBackwardTime = this.player.getCurrentTime();
            this.player.seekTo(Math.max(0, currentBackwardTime - value), true);
            break;
          case 'mute':
            this.player.mute();
            break;
          case 'unmute':
            this.player.unMute();
            break;
          case 'seek':
            // control페이지에서 전송한 명령
            this.player.seekTo(value, true);
            this.player.playVideo();
            break;
          default:
            console.log('Unknown command:', command);
        }
      }
    });
  },
  mounted() {
    window.onpopstate = (event) => {
      window.location.href = '/index';
    };
  
    history.replaceState({}, '', window.location.href);
    
    window.onYouTubeIframeAPIReady = () => {
      console.log("YouTube IFrame API is ready");
      if (this.initializePlayer) {
        this.initializePlayer();
      } else {
        console.warn("initializePlayer not defined");
      }
    };
  },
  methods: {
    handleSubtitleClick(subtitle) {
      const timeRegex = /\[(\d{2}):(\d{2})\]/;
      const match = subtitle.match(timeRegex);

      if (match) {
        const minutes = parseInt(match[1], 10);
        const seconds = parseInt(match[2], 10);
        const totalTime = minutes * 60 + seconds;
        console.log(`Seeking to time: ${totalTime} seconds`);
        if (this.player) {
          this.player.seekTo(totalTime, true);
          this.player.playVideo();
        }
      } else {
        console.error("No valid time found in subtitle.");
      }
    },

    initializePlayer() {
      console.log("initializePlayer called");
      this.player = new YT.Player('player', {
        height: '460',
        width: '640',
        videoId: this.video_id,
        events: {
          'onReady': this.onPlayerReady
        }
      });
    },

    onPlayerReady(event) {
      console.log("Player ready");
      const loadingEl = document.getElementById('loading');
      const appEl = document.getElementById('app');
      if (loadingEl) loadingEl.style.display = 'none';
      if (appEl) appEl.classList.remove('hidden');
    },

    joinRoom() {
      if (this.currentPin) {
        socket.emit('join', { pin: this.currentPin });
        // subtitle_update도 필요하다면 여기에서 처리
        socket.on('subtitle_update', (data) => {
          console.log("subtitle_update 수신:", data.subtitle);
          this.subtitleText = data.subtitle || '';
          this.parseSubtitles();
        });
        
        if (this.script && this.script.length > 0) {
          const subtitleText = this.script.join('\n'); // 배열을 줄바꿈으로 합침
          socket.emit('subtitle_update', { pin: this.currentPin, subtitle: subtitleText });
        }        
        return true;
      } else {
        console.log("PIN을 입력하세요.");
        return false;
      }
    },

    handleControllerClick() {
      const joined = this.joinRoom();
    
      if (joined) {
        this.showQRCode = !this.showQRCode;
    
        if (this.showQRCode) {
          this.generateQRCode();
        } else {
          const qrContainer = document.getElementById('qr-code-container');
          if (qrContainer) {
            qrContainer.innerHTML = '';
          }
        }
      } else {
        console.log("룸 참가에 실패했습니다. PIN을 확인하세요.");
      }
    },
    
    generateQRCode() {
      // QR 코드로 이동할 URL (control.html 경로에 PIN 쿼리 파라미터)
      const url = `${window.location.origin}/control?pin=${this.currentPin}`;
    
      this.$nextTick(() => {
        const qrContainer = document.getElementById('qr-code-container');
        qrContainer.innerHTML = ''; // QR 코드 컨테이너 초기화
        new QRCode(qrContainer, {
          text: url,
          width: 180,
          height: 180,
        });
      });
    },
  }
});

appInstance.mount('#app');
