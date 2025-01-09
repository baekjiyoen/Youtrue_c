from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, emit
from db import get_db_connection
import random, json
import uuid
import threading
from src.mainpy import *

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

pin_to_video = {}
rooms = []
room_members = {}
rooms_data = {}
existing_usernames = []

def generate_pin(length=4):
    while True:
        new_pin = str(random.randint(0, 9999)).zfill(length)
        if new_pin not in pin_to_video:
            return new_pin

def assign_pin_to_video(video_id):
    new_pin = generate_pin()
    pin_to_video[new_pin] = video_id
    return new_pin

# -------------------------------------------------
# 방 생성 시, rooms_data[room_id] 기본 구조
# -------------------------------------------------
def init_room_data(room_id, video_id='BBmKnbPRzbM'):
    # 해당 방에 대한 기본값이 없으면 초기화
    if room_id not in rooms_data:
        rooms_data[room_id] = {
            "video_id": video_id,
            "currentTime": 0,
            "isPlaying": False,
            "chat_history": []
        }

# -------------------------------------------------
# 유저 목록 broadcast
# -------------------------------------------------
def update_user_list(room_id):
    user_list = list(room_members.get(room_id, {}).values())
    emit('user_list', {'users': user_list}, room=room_id)

# ===================================
# ** soket 관련
# ===================================

@socketio.on('join')
def on_join(data):
    pin = data.get('pin')
    if pin and pin in pin_to_video:
        room = pin
        join_room(room)
        emit('message', f'PIN {room} 방에 접속하였습니다.', room=room)
    else:
        emit('error', '유효하지 않은 PIN입니다.')

@socketio.on('command')
def handle_command(data):
    pin = data.get('pin')
    if pin and pin in pin_to_video:
        emit('command', data, room=pin, broadcast=True)
    else:
        emit('error', '유효하지 않은 PIN입니다.')

@socketio.on('subtitle_update')
def handle_subtitle_update(data):
    pin = data.get('pin')
    subtitle = data.get('subtitle', '')
    if pin and pin in pin_to_video:
        emit('subtitle_update', {'subtitle': subtitle}, room=pin)
    else:
        emit('error', '유효하지 않은 PIN입니다.')

@socketio.on('create_room')
def handle_create_room(data):
    """단순히 방 이름을 입력 받아 새 room_id를 생성"""
    room_name = data.get('name')
    if not room_name:
        return emit('error', '방 이름이 필요합니다.')

    room_id = str(uuid.uuid4())[:8]
    rooms.append({"id": room_id, "name": room_name})
    # 방 데이터 초기화
    init_room_data(room_id, video_id='BBmKnbPRzbM')

    socketio.emit('room_created')  # 클라이언트에 방생성 완료 알림
    print(f"[create_room] 방 생성: {room_id} / {room_name}")

@socketio.on('get_room_list')
def handle_get_room_list():
    """현재 rooms 리스트와, rooms_data에 저장된 video_id를 합쳐 전송"""
    rooms_with_video = []
    for r in rooms:
        room_id = r['id']
        video_id = rooms_data.get(room_id, {}).get('video_id', 'dQw4w9WgXcQ')
        rooms_with_video.append({
            "id": room_id,
            "name": r['name'],
            "video_id": video_id
        })
    socketio.emit('room_list', {'rooms': rooms_with_video})

@socketio.on('join_room')
def handle_join_room(data):
    username = data.get('username', '익명')
    room_id = data.get('room_id','')

    if not room_id or not username:
        emit('join_error', {'message': 'Invalid data'})
        return

    # 방에 참여시키는 로직
    join_room(room_id)
    if room_id not in room_members:
        room_members[room_id] = {}
    room_members[room_id][request.sid] = username

    init_room_data(room_id)
    update_user_list(room_id)

    join_message = f"{username}님이 입장하였습니다."
    emit('chat_message', {'sender': '', 'message': join_message}, room=room_id)


    # 비디오 상태 정보 전달
    video_id = rooms_data[room_id]['video_id']
    currentTime = rooms_data[room_id]['currentTime']
    isPlaying = rooms_data[room_id]['isPlaying']

    video_state = {
        'video_id': video_id,
        'isPlaying': isPlaying,
        'currentTime': currentTime
    }
    emit('video_info', video_state, to=request.sid)

    # 채팅 기록 전달
    chat_history = rooms_data[room_id]['chat_history']
    emit('chat_history', chat_history, to=request.sid)

    # 성공 메시지 브로드캐스트
    emit('join_success', {'message': f'{username} joined {room_id}'}, broadcast=True)


@socketio.on('video_command')
def handle_video_command(data):
    room_id = data.get('room_id')
    command = data.get('command')
    time = data.get('time', 0)
    
    current_time = data.get('time', 0)
    is_playing = data.get('isPlaying', False)

    # rooms_data에 저장
    if room_id in rooms_data:
        rooms_data[room_id]['currentTime'] = time
        if command == 'play':
            rooms_data[room_id]['isPlaying'] = True
        elif command == 'pause':
            rooms_data[room_id]['isPlaying'] = False
        elif command == 'seek':
            # 시크 명령은 곧바로 재생 상태로 감
            rooms_data[room_id]['isPlaying'] = True
    
    # 이후 다른 클라이언트에게도 중계
    emit('video_command', data, room=room_id, include_self=False)


@socketio.on('send_message')
def handle_send_message(data):
    room_id = data.get('room_id')
    text = data.get('text', '').strip()
    sender = data.get('sender', '알 수 없음')

    init_room_data(room_id)
    rooms_data[room_id]['chat_history'].append({'sender': sender, 'text': text})
    emit('chat_message', {'sender': sender, 'message': text}, room=room_id)


@socketio.on('disconnect')
def handle_disconnect():
    """
    브라우저 창 닫기 등으로 소켓 끊겼을 때
    해당 sid가 속한 방 찾아서 room_members에서 제거
    """
    sid = request.sid
    try:
        for room_id, members in room_members.items():
            if sid in members:
                del members[sid]
                update_user_list(room_id)

                # 방이 비었으면 room_empty broadcast
                if len(members) == 0:
                    emit('room_empty', room=room_id)
                break
        print(f"Client {sid} disconnected")
    except Exception as e:
        print(f"Error during disconnect: {e}")

@socketio.on_error_default
def default_error_handler(e):
    print(f"SocketIO error: {e}")

@socketio.on('change_video')
def handle_change_video(data):
    room_id = data.get('room_id')
    video_id = data.get('video_id')
    init_room_data(room_id, video_id)
    rooms_data[room_id]['video_id'] = video_id
    rooms_data[room_id]['currentTime'] = 0
    rooms_data[room_id]['isPlaying'] = True

    # 이제 rooms_data에서 꺼내서 로컬 변수로 만듦
    current_time = rooms_data[room_id]['currentTime']
    is_playing   = rooms_data[room_id]['isPlaying']

    video_state = {
        'video_id': video_id,
        'isPlaying': is_playing,
        'currentTime': current_time
    }
    emit('video_info', video_state, room=room_id)



# ===================================
# ** route관련 - 기능
# ===================================

@app.route('/progress', methods=['GET'])
def get_progress_route():
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({"error": "no job_id provided"}), 400
    
    # mainpy.py에 있는 get_progress 함수를 불러옵니다.
    progress_val = get_progress(job_id)
    
    # 진행률이 100% 이상이면 finished = True
    finished = (progress_val >= 100)
    
    return jsonify({
        "progress": progress_val,
        "finished": finished
    })


@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data.get('room_id')
    sid = request.sid
    if room_id in room_members and sid in room_members[room_id]:
        del room_members[room_id][sid]
        update_user_list(room_id)
    if room_id in room_members and len(room_members[room_id]) == 0:
        emit('room_empty', room=room_id)
        

@socketio.on('remove_room')
def handle_remove_room(data):
    room_id = data.get('room_id')
    global rooms, room_members, rooms_data
    rooms = [r for r in rooms if r['id'] != room_id]
    if room_id in room_members:
        del room_members[room_id]
    if room_id in rooms_data:
        del rooms_data[room_id]
    print(f"Room {room_id} removed")


@app.route('/api/trending-search', methods=['GET'])
def api_trending_search():
    top_search = get_trending_search()
    return jsonify({"top_search": top_search})

# prepare_data 라우트 내
@app.route('/prepare_data', methods=['POST'])
def prepare_data_route():
    data = request.get_json()
    video_id = data.get('video_id')
    if not video_id:
        return jsonify({"error": "video_id required"}), 400

    # 비동기 처리: 스레드 예시
    thread = threading.Thread(target=process_video_data, args=(video_id,))
    thread.start()

    return jsonify({"status": "started", "video_id": video_id}), 200


@app.route('/index/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        user_search = data.get('searchvedio', '').strip()
        if not user_search:
            return jsonify({"error": "검색어 없음"}), 400

        cache_record = get_search_cache(user_search)
        if cache_record and is_cache_valid(cache_record):
            video_list = json.loads(cache_record['video_list'])
            print("DB 캐시에서 검색결과 반환")
            save_real_time(user_search)
            return jsonify({"video_list": video_list})
        else:
            response = search_video(user_search)
            save_search_cache(user_search, response)
            save_real_time(user_search)
            return jsonify({"video_list": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/loading', methods=['GET'])
def loading():
    video_id = request.args.get('video_id')
    if not video_id:
        return "video_id is required", 400
    return render_template('loading.html', video_id=video_id)

@app.route('/media', methods=['POST'])
def media_page():
    video_id = request.form.get('video_id')
    if not video_id:
        return "video_id missing", 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT script, summary FROM videos WHERE video_id = %s", (video_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return "No data found for this video_id", 404

    script = json.loads(row['script'])
    summary = row['summary']
    pin = assign_pin_to_video(video_id)

    return render_template('media.html', video_id=video_id, script=script, summary=summary, pin=pin)

@socketio.on('create_room_with_video')
def handle_create_room_with_video():
    """
    별도의 video_id를 받으면 해당 영상으로 방 생성
    예: data = { 'name': '테스트방', 'video_id': 'abcdefg' }
    """
    data = request.get_json()
    room_name = data.get('name')
    video_id = data.get('video_id', 'dQw4w9WgXcQ') 
    if not room_name:
        return jsonify({"error": "방 이름이 필요합니다."}), 400

    room_id = str(uuid.uuid4())[:8]
    rooms.append({"id": room_id, "name": room_name})
    init_room_data(room_id, video_id)

    socketio.emit('room_created')
    return jsonify({"room_id": room_id})

@app.route('/index/api/recommendations', methods=['GET'])
def get_recommendations():
    video_list = get_popular_videos_and_channels()
    return jsonify({"video_list": video_list})

@app.route('/add_username', methods=['POST'])
def add_username():
    global existing_usernames
    data = request.json
    username = data.get('username', '').strip()
    if username and username not in existing_usernames:
        existing_usernames.append(username)
        return jsonify({'success': True, 'message': '닉네임이 추가되었습니다.'})
    return jsonify({'success': False, 'message': '닉네임이 이미 존재하거나 잘못되었습니다.'})


@app.route('/check_username', methods=['POST'])
def check_username():
    global existing_usernames  # 리스트를 전역 변수로 설정
    data = request.json
    username = data.get('username', '').strip()
    is_available = username not in existing_usernames
    return jsonify({'isAvailable': is_available})

# ===================================
# ** route관련 - 페이지이동 
# ===================================

@app.route('/')
def index():
    return render_template('intro.html')

@app.route('/control')
def control():
    return render_template('control.html')

@app.route('/index')
def intro():
    return render_template('index.html')

@app.route('/lobby')
def lobby():
    return render_template('lobby.html')

@app.route('/chat')
def chat_page():
    room_id = request.args.get('room_id', '')
    return render_template('chat.html', room_id=room_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
