import requests
import json
import time
import os
from tabulate import tabulate  # 표 출력을 위한 라이브러리

# API 엔드포인트 URL
URL = "http://127.0.0.1:9997/v3/paths/list"

def format_bytes(bytes_value):
    """
    바이트 값을 KB, MB, GB 단위로 변환하여 보기 좋게 포맷합니다.
    """
    if bytes_value is None:
        return "N/A"
    
    # 1024를 기준으로 계산
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes_value >= 1024 and i < len(units) - 1:
        bytes_value /= 1024.0
        i += 1
    return f"{bytes_value:.2f} {units[i]}"

def fetch_and_print_data_table(url):
    """
    지정된 URL로 GET 요청을 보내고 JSON 응답을 받아와
    주요 정보를 표(Table) 형태로 출력합니다.
    """
    try:
        # 1. HTTP GET 요청 보내기
        response = requests.get(url)
        response.raise_for_status() 

        # 2. 응답을 JSON으로 변환
        data = response.json()
        
        # 3. 표 출력을 위한 데이터 준비
        
        # 표의 헤더 정의
        headers = ["이름 (Name)", "상태 (Ready)", "트랙 (Tracks)", "수신 데이터 (Rx)", "송신 데이터 (Tx)", "준비 시간"]
        
        # 데이터 행을 저장할 리스트
        table_data = []

        if 'items' in data and data['items']:
            for item in data['items']:
                # 사람이 읽기 쉬운 형식으로 데이터 변환
                name = item.get('name', 'N/A')
                ready = "🟢 READY" if item.get('ready') else "🔴 NOT READY"
                tracks = ", ".join(item.get('tracks', []))
                
                # 바이트 값을 KB/MB/GB 등으로 변환
                bytes_rx = format_bytes(item.get('bytesReceived'))
                bytes_tx = format_bytes(item.get('bytesSent'))
                
                # 준비 시간 포맷
                ready_time = item.get('readyTime')
                if ready_time:
                    # ISO 8601 형식 문자열을 읽어서 보기 좋게 포맷합니다.
                    # 시간대 정보는 한국 시간(+09:00)이므로 별도 변환 없이 출력합니다.
                    try:
                        dt_object = time.strptime(ready_time[:19], "%Y-%m-%dT%H:%M:%S")
                        ready_time_str = time.strftime("%m-%d %H:%M:%S", dt_object)
                    except ValueError:
                        ready_time_str = str(ready_time).split('T')[0] # 파싱 오류 시 날짜만 표시
                else:
                    ready_time_str = "N/A"

                table_data.append([name, ready, tracks, bytes_rx, bytes_tx, ready_time_str])

        # 콘솔 초기화
        os.system('cls' if os.name == 'nt' else 'clear') 
        
        # 현재 시간 출력
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"--- 📊 경로 목록 업데이트: {current_time} (총 {data.get('itemCount', 0)}개 항목) ---")
        
        # 4. tabulate으로 표 출력
        # 'fancy_grid' 스타일을 사용하여 깔끔한 표를 만듭니다.
        print(tabulate(table_data, headers=headers, tablefmt="fancy_grid", numalign="right"))
        
        print("\n* 상태: 🟢 READY = 스트림 준비 완료, 🔴 NOT READY = 준비되지 않음")

    except requests.exceptions.RequestException as e:
        os.system('cls' if os.name == 'nt' else 'clear') 
        print(f"--- ⚠️ API 요청 오류 발생: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
        print(f"오류 상세: {e}")
    except Exception as e:
        os.system('cls' if os.name == 'nt' else 'clear') 
        print(f"--- ❌ 처리 중 알 수 없는 오류 발생: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
        print(f"오류 상세: {e}")


# 1초 간격으로 반복 실행
try:
    while True:
        fetch_and_print_data_table(URL)
        # 1초 대기
        time.sleep(1) 
        
except KeyboardInterrupt:
    print("\n--- 프로그램 종료 (Ctrl+C 입력됨) ---")