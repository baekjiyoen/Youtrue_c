const socket = io.connect(window.location.origin);

new Vue({
    el: '#app',
    data() {
        return {
            pin: '',
            currentPin: null,
            subtitleText: '',
            subtitleLines: []
        }
    },
    created() {
        socket.on('message', (msg) => {
            console.log('Server Message:', msg);
        });
        
        socket.on('subtitle_update', (data) => {
            console.log("subtitle_update 수신:", data.subtitle);
            this.subtitleText = data.subtitle || '';
            this.parseSubtitles();
        });

        const params = new URLSearchParams(window.location.search);
        const urlPin = params.get('pin');
        if (urlPin) {
            this.pin = urlPin.trim();
        }
    },
    mounted() {
        if (this.pin && this.pin.trim() !== '') {
            this.joinRoom();
        }
    },
    methods: {
        joinRoom() {
            const trimmedPin = this.pin.trim();
            if (trimmedPin) {
                this.currentPin = trimmedPin;
                socket.emit('join', { pin: trimmedPin });
                console.log(`PIN ${trimmedPin} 룸에 접속 시도`);
            } else {
                console.log("PIN을 입력하세요.");
            }
        },
        sendCommand(command, value = null) {
            if (this.currentPin) {
                const data = { pin: this.currentPin, command: command };
                if (value !== null) {
                    data.value = value;
                }
                socket.emit('command', data);
                console.log(`명령 전송: ${command}`, data);
            } else {
                console.log("PIN으로 룸에 접속 후 명령을 전송하세요.");
            }
        },
        parseSubtitles() {
            console.log("원본 자막 텍스트:", this.subtitleText);
            this.subtitleLines = this.subtitleText.split('\n');
            console.log("파싱 후 라인:", this.subtitleLines);
        },
        
        handleSubtitleClick(subtitle) {
            const cleanSubtitle = subtitle.replace(/<[^>]*>/g, '');
          
            const timeRegex = /\[(\d{2}):(\d{2})\]/;
            const match = cleanSubtitle.match(timeRegex);
        
            if (match) {
                const minutes = parseInt(match[1], 10);
                const seconds = parseInt(match[2], 10);
                const totalTime = minutes * 60 + seconds;
                console.log(`Requesting seek to time: ${totalTime} seconds`);
        
                this.sendCommand('seek', totalTime);
            } else {
                console.error("No valid time found in subtitle.");
            }
        }
    }
});
