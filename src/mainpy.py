import json
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from googleapiclient.discovery import build
import isodate
from youtube_transcript_api import YouTubeTranscriptApi
from itertools import zip_longest
import requests
from googleapiclient.errors import HttpError
import urllib.request
from db import get_db_connection
from datetime import datetime, timedelta
import time
import torch
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast

api_key_path2 = '/home/hserver/project/yourvideopro/important/01_G/APIkey.json'
MODEL_DIR = "model"

def load_gemini_api_key():
    api_key_path = "important/01_G/APIkey.json"
    try:
        with open(api_key_path, 'r') as file:
            data = json.load(file)
            print("모든 API 키 로딩이 완료되었습니다.")
            return data.get('Gemini'), data.get('Youtube'), data.get('Naver_ID'), data.get('Naver_KEY')
    except:
        pass
    try:
        with open(api_key_path2, 'r') as file:
            data = json.load(file)
            print("임시 API 키 로딩이 완료되었습니다.")
            return data.get('Gemini'), data.get('Youtube'), data.get('Naver_ID'), data.get('Naver_KEY')
    except FileNotFoundError:
        print("API 키 파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError:
        print("API 키 파일의 JSON 형식이 올바르지 않습니다.")
        return None
    
gemini_key, youtube_key, naver_id, naver_key = load_gemini_api_key()

if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(model_name = "gemini-1.5-pro")
        print("Gemini 로딩이 완료되었습니다.")
    except Exception as e:
        print(f"Gemini 모델 생성 오류: {e}")

print('''
          환영합니다!
          **로컬환경 접속 url**
          http://localhost:5000/
          오늘도 화이팅!
          ''')

search_cache = {}

# 진행률 관련 전역 변수 및 함수
job_progress = {}

def update_progress(job_id, current_line, total_lines, force_final=False, non_script=False):
    if non_script:
        job_progress[job_id] = 100
        return
    
    if force_final:
        # DB 반영 후 최종 100% 설정용
        job_progress[job_id] = 100
        return

    progress = int((current_line / total_lines) * 100)
    # 100%에 도달하더라도 여기서는 99%까지만 반영
    if progress >= 100:
        progress = 99
    job_progress[job_id] = progress

def get_progress(job_id):
    return job_progress.get(job_id, 0)

def search_video(search_input, max_results=10):
    if search_input in search_cache:
        print("캐시에서 검색결과 반환")
        return search_cache[search_input]
    
    def convert_duration(iso_duration):
        duration = isodate.parse_duration(iso_duration)
        total_seconds = int(duration.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        formatted_duration = f"{hours}h{minutes}m{seconds}s" if hours else f"{minutes}m{seconds}s"
        return formatted_duration, total_seconds
    
    youtube = build("youtube", "v3", developerKey=youtube_key)
    try:
        search_response = youtube.search().list(
            q=f"sub {search_input}",
            type="video",
            part="id,snippet",
            maxResults=max_results,
            videoDuration="medium"
        ).execute()
    except HttpError as e:
        print("YouTube API 호출 중 오류 발생:", e)
        return []

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    if not video_ids:
        return "검색된 동영상이 없습니다."

    try:
        video_details = youtube.videos().list(
            id=",".join(video_ids),
            part="snippet,contentDetails,statistics"
        ).execute()
    except HttpError as e:
        print("YouTube API videos() 호출 중 오류 발생:", e)
        return []

    video_data = []
    for video in video_details.get('items', []):
        duration_str = video['contentDetails']['duration']
        duration, total_seconds = convert_duration(duration_str)
        published_at = video['snippet']['publishedAt'].split('T')[0]
        video_id = video['id']

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            languages = [t.language for t in transcript_list]
        except TranscriptsDisabled:
            languages = []
        except Exception as e:
            print(f"예기치 못한 오류 발생: {e}")
            languages = []

        kor_auto = any('Korean (auto-generated)' in item for item in languages)
        kor = any('Korean' in item and '(auto-generated)' not in item for item in languages)
        eng = any('English' in item for item in languages)

        if kor and eng:
            captions_info = "한글 및 영어 자막 지원"
        elif kor:
            captions_info = "한글 자막 지원"
        elif eng:
            captions_info = "영어 자막 지원"
        elif kor_auto:
            captions_info = "한글(자동번역) 자막 지원"
        else:
            captions_info = "자막 없음"

        video_info = {
            "video_id": video_id,
            "title": video['snippet']['title'],
            "published_at": published_at,
            "thumbnail_url": video['snippet']['thumbnails']['high']['url'],
            "duration": duration,
            "view_count": video['statistics'].get('viewCount', 0),
            "like_count": video['statistics'].get('likeCount', 0),
            "captions_info": captions_info
        }
        video_data.append(video_info)

    search_cache[search_input] = video_data
    return video_data

def media_script(video_id, job_id):
    def summary_ge(answer_ko_script):
        cleaned_list = []
        for line in answer_ko_script:
            if "한글:" in line:
                parts = line.split("한글:", 1)
                cleaned_line = parts[1].strip()
                cleaned_list.append(cleaned_line)
            else:
                cleaned_list.append(line)
        
        answer_ko_script = " ".join(cleaned_list)
        
        prompt = f'''다음의 내용을 요약해줘

        내용:
        {answer_ko_script}
        '''
        
        prompt = prompt.replace("\n", "").replace("\\","")
        response = model.generate_content(prompt)
        answer = response.candidates[0].content.parts[0].text
        
        answer = answer.strip()
        answer = answer.replace("'","")
        return answer
    
    def summary(scripts):
        def test_model(input_text, model_dir=MODEL_DIR, max_source_length=1024, max_target_length=128):
            """
            학습 완료된 KoBART 모델로 요약을 수행하는 함수
            """
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # 1) 토크나이저 / 모델 불러오기
            tokenizer = PreTrainedTokenizerFast.from_pretrained(model_dir)
            model = BartForConditionalGeneration.from_pretrained(model_dir)

            model.to(device)
            model.eval()

            # 2) 입력 텍스트 토큰화
            inputs = tokenizer(
                input_text,
                return_tensors="pt",
                max_length=max_source_length,
                truncation=True
            ).to(device)

            # 3) 요약 생성 (샘플링 or 빔서치)
            with torch.no_grad():
                summary_ids = model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                    num_beams=4,
                    max_length=max_target_length,
                    early_stopping=True
                )

            # 4) 디코딩
            summary_text = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            
            return summary_text

        def split_and_summarize(scripts, model_dir=MODEL_DIR):
            chunks = [scripts[i:i+1024] for i in range(0, len(scripts), 1024)]
            summaries = []
            for chunk in chunks:
                summary = test_model(chunk, model_dir=model_dir)
                if len(summary) >= 50:  # 조건 완화
                    summaries.append(summary)
            return summaries

        def summarize_final(summaries, model_dir=MODEL_DIR):
            """
            개별 요약 정보를 다시 하나로 합쳐 최종 요약을 생성하는 함수
            """
            combined_text = " ".join(summaries)
            final_summary = test_model(combined_text, model_dir=model_dir)
            return final_summary
        
        cleaned_list = []
        
        for line in scripts:
            if "한글:" in line:
                parts = line.split("한글:", 1)
                cleaned_line = parts[1].strip()
                cleaned_list.append(cleaned_line)
            else:
                cleaned_list.append(line)
        
        scripts = " ".join(cleaned_list)

        # 요약 실행
        summaries = split_and_summarize(scripts)
        resurt_summary = ''

        # 요약 결과 출력
        if summaries:
            for idx, summary in enumerate(summaries):
                resurt_summary += f"\n요약 {idx + 1} : {summary}"

            # 최종 요약 생성
            final_summary = summarize_final(summaries)
            resurt_summary += f"\n최종 요약 : {final_summary}"
        else:
            print("===== 요약 결과 없음 =====")
        
        return resurt_summary
    
    def get_caption_info(video_id):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            languages = [t.language for t in transcript_list]
            return {"captions_available": True, "languages": languages}
        except TranscriptsDisabled:
            return {"captions_available": False, "languages": []}
        except Exception as e:
            return {"captions_available": False, "languages": [], "error": str(e)}
    
    def transcript(text, input_language, output_language):
        client_id = naver_id
        client_secret = naver_key

        encText = urllib.parse.quote(text)
        data = f"source={input_language}&target={output_language}&text={encText}"
        url = "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation"
        request = urllib.request.Request(url)
        request.add_header("X-NCP-APIGW-API-KEY-ID",client_id)
        request.add_header("X-NCP-APIGW-API-KEY",client_secret)
        response = urllib.request.urlopen(request, data=data.encode("utf-8"))
        rescode = response.getcode()
        if(rescode==200):
            response_body = response.read()
            time.sleep(0.01)
            return response_body.decode('utf-8')
        else:
            print("Error Code:" + rescode)

    # 진행률 계산을 위해 각 sub_fc에서 총 라인 수 파악
    caption_info = get_caption_info(video_id)
    kor_auto = any('Korean (auto-generated)' in item for item in caption_info["languages"])
    kor = any('Korean' in item and '(auto-generated)' not in item for item in caption_info["languages"])
    eng = any('English' in item for item in caption_info["languages"])

    def sub_fc1(video_id, job_id):
        transcript_ko = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        transcript_en = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        script = []
        ko_script = []
        
        total_lines = len(transcript_ko)*2
        current_line = 0

        default_value = {"text": "", "start": 0, "duration": 0}
        for ko, en in zip_longest(transcript_ko, transcript_en, fillvalue=default_value):
            start_ko = ko['start']
            start_en = en['start']
            min_ko = int(start_ko // 60)
            sec_ko = int(start_ko % 60)
            min_en = int(start_en // 60)
            sec_en = int(start_en % 60)
            
            script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko['text']}")
            ko_script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko['text']}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

            script.append(f"[{min_en:02}:{sec_en:02}] 영어: {en['text']}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

        return script, ko_script

    def sub_fc2(video_id, job_id):
        transcript_ko = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        script = []
        ko_script = []
        
        total_lines = len(transcript_ko)*2
        current_line = 0

        for ko in transcript_ko:
            min_ko = int(ko['start'] // 60)
            sec_ko = int(ko['start'] % 60)
            ko_text = ko['text']
            en_text = transcript(ko_text, input_language='ko', output_language='en')
            # 파파고 번역으로 사용
            en_text = json.loads(en_text)
            en_text = en_text["message"]["result"]["translatedText"]
            
            script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko_text}")
            ko_script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)
            
            script.append(f"[{min_ko:02}:{sec_ko:02}] 영어: {en_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

        return script, ko_script

    def sub_fc3(video_id, job_id):
        transcript_en = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        script = []
        ko_script = []

        total_lines = len(transcript_en)*2
        current_line = 0
        
        for en in transcript_en:
            min_en = int(en['start'] // 60)
            sec_en = int(en['start'] % 60)
            en_text = en['text']
            ko_text = transcript(en_text, input_language='en', output_language='ko')
            ko_text = json.loads(ko_text)
            ko_text = ko_text["message"]["result"]["translatedText"]
            
            script.append(f"[{min_en:02}:{sec_en:02}] 한글: {ko_text}")
            ko_script.append(f"[{min_en:02}:{sec_en:02}] 한글: {ko_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

            script.append(f"[{min_en:02}:{sec_en:02}] 영어: {en_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

        return script, ko_script
    
    def sub_fc4(video_id, job_id):
        transcript_ko = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        script = []
        ko_script = []

        total_lines = len(transcript_ko)*2
        current_line = 0
        
        for ko in transcript_ko:
            min_ko = int(ko['start'] // 60)
            sec_ko = int(ko['start'] % 60)
            ko_text = ko['text']
            en_text = transcript(ko_text, input_language='ko', output_language='en')
            en_text = json.loads(en_text)
            en_text = en_text["message"]["result"]["translatedText"]
            
            script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko_text}")
            ko_script.append(f"[{min_ko:02}:{sec_ko:02}] 한글: {ko_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

            script.append(f"[{min_ko:02}:{sec_ko:02}] 영어: {en_text}")
            current_line += 1
            update_progress(job_id, current_line, total_lines)

        return script, ko_script

    if kor and eng:
        script, ko_script = sub_fc1(video_id, job_id)
    elif kor:
        script, ko_script = sub_fc2(video_id, job_id)
    elif eng:
        script, ko_script = sub_fc3(video_id, job_id)
    elif kor_auto:
        script, ko_script = sub_fc4(video_id, job_id)
    else:
        update_progress(None, None, None, non_script=True)
        return ["해당영상은 자막정보를 제공하지않습니다."], "자막정보를 제공하지 않는 동영상은 AI요약정보를 제공하지 않습니다."
    
    ko_summary = ''
    ko_summary += "-- GEMINI 요약 --\n" + summary_ge(ko_script)
    ko_summary += "\n\n-- you_model 요약 --\n" + summary(ko_script)
    
    return script, ko_summary

def get_search_cache(search_query):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM search_cache WHERE search_query = %s", (search_query,))
        return cursor.fetchone()
    except Exception as e:
        print("DB 조회 중 오류:", e)
        return None
    finally:
        cursor.close()
        conn.close()

def save_search_cache(search_query, video_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO search_cache (search_query, video_list, cached_at, count)
        VALUES (%s, %s, NOW(), 1)
        ON DUPLICATE KEY UPDATE
        video_list = VALUES(video_list),
        cached_at = NOW(),
        count = count + 1
        """
        cursor.execute(query, (search_query, json.dumps(video_list)))
        conn.commit()
    except Exception as e:
        print("DB 저장 중 오류:", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def save_real_time(search_query):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = """
        INSERT INTO real_time (search_query, cached_at)
        VALUES (%s, %s)
        """
        cursor.execute(query, (search_query, current_time))
        conn.commit()
    except Exception as e:
        print("real_time 테이블 저장 중 오류:", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def is_cache_valid(cache_record):
    if not cache_record:
        return False
    cached_at = cache_record['cached_at']
    return cached_at > datetime.now() - timedelta(hours=1)

def get_popular_videos_and_channels(region_code='KR', max_results=10):
    BASE_URL = 'https://www.googleapis.com/youtube/v3'
    video_url = f"{BASE_URL}/videos"
    params = {
        'part': 'snippet',
        'chart': 'mostPopular',
        'regionCode': region_code,
        'maxResults': max_results,
        'key': youtube_key,
    }
    response = requests.get(video_url, params=params)
    videos = response.json()

    results = []
    channel_ids = set()

    for video in videos.get('items', []):
        video_id = video['id']
        video_title = video['snippet']['title']
        thumbnail_url = video['snippet']['thumbnails'].get('standard', {}).get('url')
        channel_id = video['snippet']['channelId']
        channel_title = video['snippet']['channelTitle']

        if channel_id not in channel_ids:
            channel_ids.add(channel_id)

        results.append({
            'video_id': video_id,
            'video_title': video_title,
            'thumbnail_url': thumbnail_url,
            'channel_id': channel_id,
            'channel_title': channel_title,
            'profile_image_url': None
        })

    if channel_ids:
        channel_url = f"{BASE_URL}/channels"
        params = {
            'part': 'snippet',
            'id': ','.join(channel_ids),
            'key': youtube_key
        }
        channel_response = requests.get(channel_url, params=params)
        channel_data = channel_response.json()

        channel_profiles = {
            item['id']: item['snippet']['thumbnails']['default']['url']
            for item in channel_data.get('items', [])
        }

        for result in results:
            result['profile_image_url'] = channel_profiles.get(result['channel_id'])

    return results

def get_trending_search():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT search_query
        FROM real_time_search
        WHERE DATE(cached_at) = CURDATE()
        ORDER BY count DESC
        LIMIT 5;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        top_search = []
        for search in results:
            top_search.append(search['search_query'])

        return top_search
    except Exception as e:
        print("데이터 조회 중 오류:", e)
        return []
    finally:
        cursor.close()
        conn.close()

def process_video_data(video_id):
    print(f"process_video_data 시작: video_id={video_id}")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    job_id = video_id
    job_progress[job_id] = 0  # 초기화

    try:
        print("DB 조회")
        cursor.execute("SELECT * FROM videos WHERE video_id = %s", (video_id,))
        existing_data = cursor.fetchone()
        print(f"existing_data: {existing_data}")

        if existing_data:
            script = json.loads(existing_data['script'])
            summary = existing_data['summary']
            print("기존 데이터 사용")
        else:
            print("media_script 호출 전")
            # job_id를 매개변수로 추가
            script, summary = media_script(video_id, job_id)
            print("media_script 완료")

        print("DB INSERT 시작")
        query = """
        INSERT INTO videos (video_id, script, summary, count)
        VALUES (%s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE
          script = VALUES(script),
          summary = VALUES(summary),
          count = count + 1
        """
        
        print("DB INSERT 직전")
        cursor.execute(query, (video_id, json.dumps(script), summary))
        print("DB INSERT 직후, commit 전")
        conn.commit()
        print("DB commit 완료")

        # 새로운 커넥션으로 재확인
        test_conn = get_db_connection()
        test_cursor = test_conn.cursor(dictionary=True)
        print("DB 재조회 시작")
        test_cursor.execute("SELECT script FROM videos WHERE video_id = %s", (video_id,))
        check_row = test_cursor.fetchone()
        test_cursor.close()
        test_conn.close()

        if check_row:
            print("DB 반영 확인 후 진행률 100%")
            update_progress(job_id, 0, 0, force_final=True) 
        else:
            print("DB 반영 확인 실패 - 데이터 미조회")

        return {"video_id": video_id}
    except Exception as e:
        conn.rollback()
        print("process_video_data 에러 발생:", e)
        raise e
    finally:
        cursor.close()
        conn.close()
