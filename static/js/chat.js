const app = Vue.createApp({
  data() {
    return {
      // 채팅 관련
      users: [],
      messages: [],
      socket: null,
      roomId: '',
      username: '',
      isUsernameSet: false,
      socket:null,

      // 영상/플레이어 관련
      videoId: '', // 서버에서 video_info 수신 후 세팅
      startTime: 0,
      isPlaying: false,
      lastKnownTime: 0,
      timeThreshold: 1,
      ignoreFirstStateChange: false,

      // 시크 직후 발생하는 자동 pause 등 이벤트 무시용
      lastSeekTime: 0, // 시크 시점 기록 (ms)

      // UI
      isMenuOpen: false,
      isEmojiPanelVisible: false,
      isRoomEmpty: false,
      isLoading: false,
      searchInput: "",
      videoResults: [],
      emojis: [
        { name: 'achy', src: '/static/image/emojis/achy.png' },
        { name: 'angel', src: '/static/image/emojis/angel.png' },
        { name: 'cold', src: '/static/image/emojis/cold.png' },
        { name: 'cry2', src: '/static/image/emojis/cry2.png' },
        { name: 'dubious', src: '/static/image/emojis/dubious.png' },
        { name: 'hungry', src: '/static/image/emojis/hungry.png' },
        { name: 'lol', src: '/static/image/emojis/lol.png' },
        { name: 'love', src: '/static/image/emojis/love.png' },
        { name: 'money', src: '/static/image/emojis/money.png' },
        { name: 'near and dear', src: '/static/image/emojis/near and dear.png' },
        { name: 'quippy', src: '/static/image/emojis/quippy.png' },
        { name: 'sad', src: '/static/image/emojis/sad.png' },
        { name: 'sleep', src: '/static/image/emojis/sleep.png' },
        { name: 'smile', src: '/static/image/emojis/smile.png' },
        { name: 'sorrowful', src: '/static/image/emojis/sorrowful.png' },
        { name: 'disausting', src: '/static/image/emojis/disausting.png' },
        { name: 'heartsore', src: '/static/image/emojis/heartsore.png' },
        { name: 'optimistic', src: '/static/image/emojis/optimistic.png' },
        { name: 'affronted', src: '/static/image/emojis/affronted.png' },
      ],
    };
  },

  mounted() {
    
        this.socket = io();
    // 방 ID 추출
    const params = new URLSearchParams(window.location.search);
    this.roomId = params.get('room_id');

    // 소켓 연결
    this.socket = io(window.location.origin);

    // 소켓 이벤트 설정
    this.setupSocketEvents();
    // 사용자 목록 업데이트 이벤트 수신
    this.socket.on('update_user_list', (data) => {
      this.users = data.users; // 서버에서 받은 사용자 목록 업데이트
    });
    this.socket.on('chat_message', (data) => {
      const isMe = (data.sender === this.username);
      this.addMessage(data.sender, data.message, isMe);
    });
  },

  

  methods: {

    /**************************************************************
     * 1) 시크(Seek) 메서드: 시점을 이동 -> "seek" 명령으로 전송
     **************************************************************/
    goToTime(newTime) {
      if (window.youtubePlayer) {
        window.youtubePlayer.seekTo(newTime, true);
        window.youtubePlayer.playVideo();
        this.isPlaying = true;
    
        // 시크 직후 시점 기록
        this.lastSeekTime = Date.now();
      }
    
      // 서버로도 시크 정보 emit
      this.socket.emit('video_command', {
        command: 'seek',
        room_id: this.roomId,
        time: newTime,
        isPlaying: true
      });
    },

    /**************************************************************
     * 2) 새 영상 선택
     **************************************************************/
    selectVideo(videoId) {
      console.log("selectVideo called with:", videoId);
      this.isPlaying = true; // 영상 교체 시 재생 상태로
      this.socket.emit('change_video', {
        room_id: this.roomId,
        video_id: videoId
      });
    },

    /**************************************************************
     * 3) 소켓 이벤트 설정
     **************************************************************/
    setupSocketEvents() {
      // 채팅 기록
      
      this.socket.on('chat_history', (chatLogs) => {
        chatLogs.forEach(log => {
          this.addMessage(log.sender, log.text, false);
        });
      });
      
      this.socket.off('chat_message');
      // 채팅 메시지
      this.socket.on('chat_message', (data) => {
        if (data.sender !== this.username) {
          this.addMessage(data.sender, data.text, false);
        }
      });

      // 사용자 목록
      this.socket.on('user_list', (data) => {
        this.updateUserList(data.users);
      });

      // 서버에서 현재 영상 정보 전달
      this.socket.on('video_info', (data) => {
        console.log("Received video_info:", data);
        this.videoId   = data.video_id;
        this.isPlaying = data.isPlaying;
        this.startTime = data.currentTime;

        if (!window.youtubePlayer) {
          this.createPlayer();
        } else {
          this.setupPlayer();
        }
      });

      // ***********************************************************
      // video_command (play/pause/seek) 수신부
      // ***********************************************************
      this.socket.on('video_command', (data) => {
        if (!window.youtubePlayer) return;

        const currentTime = window.youtubePlayer.getCurrentTime();
        const requestedTime = data.time || 0;
        const timeDiff = Math.abs(requestedTime - currentTime);

        if (data.command === 'seek') {
          // (1) 시점을 이동
          // timeDiff 조건을 완화 or 제거 -> 무조건 시크
          window.youtubePlayer.seekTo(requestedTime, true);

          // (2) 곧바로 재생
          this.isPlaying = true;
          window.youtubePlayer.playVideo();

          // 시크 직후 시점 기록
          this.lastSeekTime = Date.now();

        } else if (data.command === 'play') {
          this.isPlaying = true;
          // 선택적으로 timeDiff>0.5 시 seek
          if (timeDiff > 0.5) {
            window.youtubePlayer.seekTo(requestedTime, true);
          }
          window.youtubePlayer.playVideo();

        } else if (data.command === 'pause') {
          this.isPlaying = false;
          if (timeDiff > 0.5) {
            window.youtubePlayer.seekTo(requestedTime, true);
          }
          window.youtubePlayer.pauseVideo();

        } else {
          console.log("Unknown command:", data.command);
        }
      });

      // 방이 비었을 때
      this.socket.on('room_empty', () => {
        this.isRoomEmpty = true;
        this.askRemoveRoom();
      });
    },

    /**************************************************************
     * 4) 닉네임 설정
     **************************************************************/
    confirmUsername() {
      const name = this.username.trim();
      if (!name) {
        alert('닉네임을 입력해주세요.');
        return;
      }
   
      // 서버로 닉네임 중복 체크 요청
      fetch('/check_username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: name }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.isAvailable) {
            // 닉네임 추가 요청
            fetch('/add_username', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ username: name }),
            })
              .then((response) => response.json())
              .then((addResponse) => {
                if (addResponse.success) {
                  alert(`닉네임 "${name}"으로 설정되었습니다.`);
                } else {
                  alert(addResponse.message);
                }
              });
          } else {
            alert('이미 사용 중인 닉네임입니다. 다른 닉네임을 입력해주세요.');
            this.isUsernameSet = false;
          }
        })
        .catch((error) => {
          console.error('Error:', error);
        });
        this.isUsernameSet = true;

        this.socket.emit('join_room', { room_id: this.roomId, username: this.username });
      },
    

    /**************************************************************
     * 5) 유튜브 플레이어
     **************************************************************/
    createPlayer() {
      if (!window.youtubePlayer) {
        console.log("Creating YT.Player with videoId:", this.videoId);
        window.youtubePlayer = new YT.Player('player', {
          videoId: this.videoId || 'BBmKnbPRzbM',
          events: {
            'onReady': (event) => {
              console.log("Player onReady");
              event.target.seekTo(this.startTime, true);
              this.lastKnownTime = this.startTime;
            },
            'onStateChange': this.onPlayerStateChange
          }
        });
      }
      this.ignoreFirstStateChange = true;
      this.setupPlayer();
    },

    setupPlayer() {
      if (window.youtubePlayer && typeof window.youtubePlayer.loadVideoById === 'function') {
        window.youtubePlayer.loadVideoById(this.videoId || 'BBmKnbPRzbM', this.startTime);
        if (this.isPlaying) {
          window.youtubePlayer.playVideo();
        } else {
          window.youtubePlayer.pauseVideo();
        }
      }
    },

    onPlayerStateChange(event) {
      const state = event.data;
    
      // (0) 첫 onReady 이벤트 무시
      if (this.ignoreFirstStateChange) {
        this.ignoreFirstStateChange = false;
        return;
      }
    
      // (0-1) 시크 도중 발생하는 자동 pause 무시용 (옵션)
      if (this.isSeekingManually) {
        return;
      }
    
      // (1) "시크 직후 3초 이내 발생하는 PAUSED"이면 무시하고 자동으로 playVideo()
      const now = Date.now();
      if (now - this.lastSeekTime < 3000 && state === YT.PlayerState.PAUSED) {
        console.log("Ignore auto pause: within 3s after seek => replay");
        window.youtubePlayer.playVideo();
        return;
      }
    
      // (2) 버퍼링 상태(BUFFERING)에서 즉시 재생 시도
      if (state === YT.PlayerState.BUFFERING) {
        console.log("Player is buffering... let's try keep playing");
        window.youtubePlayer.playVideo();
        return;
      }
    
      // (3) 기존 로직: PLAY/PAUSE 외에는 무시
      if (state !== YT.PlayerState.PLAYING && state !== YT.PlayerState.PAUSED) {
        return;
      }
    
      // (4) 지금 시점이 마지막으로 인식한 시점과 0.3초 이내면 무시
      const currentTime = window.youtubePlayer.getCurrentTime();
      const timeDiff = Math.abs(currentTime - this.lastKnownTime);
      if (timeDiff < 0.3) {
        return;
      }
    
      // (5) play인지 pause인지
      const isPlaying = (state === YT.PlayerState.PLAYING);
    
      // (6) 시크 직후 3초 경과 후 발생한 pause/play만 서버에 전송
      //     (혹은 auto-pause가 아니라 '의도된' pause/play만 전송)
      this.socket.emit('video_command', {
        room_id: this.roomId,
        command: isPlaying ? 'play' : 'pause',
        time: currentTime,
        isPlaying
      });
    
      // (7) 마지막으로 알려진 시점 갱신
      this.lastKnownTime = currentTime;
    },
    

    /**************************************************************
     * 6) play/pause 버튼
     **************************************************************/
    playVideo() {
      if (window.youtubePlayer) {
        window.youtubePlayer.playVideo();
        const currentTime = window.youtubePlayer.getCurrentTime();
        this.socket.emit('video_command', {
          room_id: this.roomId,
          command: 'play',
          time: currentTime,
          isPlaying: true
        });
        this.lastKnownTime = currentTime;
      }
    },

    pauseVideo() {
      if (window.youtubePlayer) {
        window.youtubePlayer.pauseVideo();
        const currentTime = window.youtubePlayer.getCurrentTime();
        this.socket.emit('video_command', {
          room_id: this.roomId,
          command: 'pause',
          time: currentTime,
          isPlaying: false
        });
        this.lastKnownTime = currentTime;
      }
    },

    /**************************************************************
     * 7) 채팅 로직
     **************************************************************/
    sendMessage() {
      const input = this.$refs.messageInput;
      const text = input.innerText.trim();
      const htmlContent = input.innerHTML.trim();

      if (text || htmlContent) {
        // 서버로만 메시지 전송, 여기서는 addMessage 호출 X
        this.socket.emit('send_message', {
          room_id: this.roomId,
          sender: this.username,
          text: htmlContent
        });
    
        input.innerText = '';
        this.scrollToBottom();
      }
    
      if (!text.trim()) return;
    },

    addMessage(sender, text, isMe = false) {
      this.messages.push({ sender, text, isMe });
      this.$nextTick(() => {
        this.scrollToBottom();
      });
    },

    scrollToBottom() {
      const container = this.$refs.chatMessages;
      if (container) container.scrollTop = container.scrollHeight;
    },

    exitApp() {
      this.socket.emit('leave_room', { room_id: this.roomId, username: this.username });
    },

    askRemoveRoom() {
      const result = confirm("이 방에 인원이 0명이면 방이 제거됩니다.\n방을 제거하시겠습니까?");
      if (result) {
        this.socket.emit('remove_room', { room_id: this.roomId });
      }
      window.location.href = "/lobby";
    },

    updateUserList(users) {
      this.users = users;
    },

    toggleUserList() {
      this.isMenuOpen = !this.isMenuOpen;
    },

    toggleEmojiPanel() {
      this.isEmojiPanelVisible = !this.isEmojiPanelVisible;
    },

    addEmojiToInput(emojiSrc) {
      const input = this.$refs.messageInput;
      input.innerHTML += `<img src="${emojiSrc}" alt="emoji" class="inline-emoji" />`;
      input.focus();
    },

    truncatedTitle(title, maxLength) {
      if (!title) return '';
      return title.length > maxLength ? title.substring(0, maxLength) + '...' : title;
    },

    async search() {
      const searchInput = this.searchInput.trim();
      if (!searchInput) {
        alert("검색어를 입력하세요.");
        return;
      }
      this.isLoading = true;

      try {
        const response = await fetch("/index/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ searchvedio: searchInput }),
        });
        const data = await response.json();
        this.isLoading = false;

        if (data.error) {
          console.error("서버 에러:", data.error);
          alert("검색 중 오류가 발생했습니다: " + data.error);
          this.videoResults = [];
        } else {
          this.videoResults = data.video_list || [];
        }
      } catch (error) {
        console.error("검색 중 오류 발생:", error);
        alert("검색 중 오류가 발생했습니다.");
        this.isLoading = false;
        this.videoResults = [];
      }
    }
  },
});

app.mount('#app');