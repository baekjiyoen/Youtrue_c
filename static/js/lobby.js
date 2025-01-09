const { createApp } = Vue

      createApp({
        data() {
          return {
            socket: null,
            rooms: [],
            roomName: '',
            showTooltip: false,
            isHovered: false,
          }
        },
        methods: {
          loadRooms() {
            this.socket.emit('get_room_list');
          },
          createRoom() {
            const name = this.roomName.trim();
            if (!name) {
              alert('방 이름을 입력하세요.');
              return;
            }
            this.socket.emit('create_room', { name });
          },
          goToChat(roomId) {
            // 닉네임 없이 바로 chat 페이지로 이동
            window.location.href = `/chat?room_id=${roomId}`;
          }
        },
        mounted() {
          this.socket = io(window.location.origin);

          this.socket.on('room_list', (data) => {
            this.rooms = data.rooms;
          });

          this.socket.on('room_created', () => {
            this.roomName = '';
            this.loadRooms();
          });

          // join_room 이벤트 발생 시 서버에서 enter_chat를 보냈지만 지금은 lobby에서 보내지 않으므로 제거

          // 페이지 로드시 자동으로 방 목록 요청
          this.loadRooms();
        },
        createRoom() {
          if (this.roomName.trim()) {
            alert(`방 "${this.roomName}"이 생성되었습니다!`);
            this.roomName = '';
          }
        }
      }).mount('#app');