1. 프로젝트 이름
Sunmoon University Festival Web Platform (선문대 축제 웹사이트)

3. 프로젝트 개요
선문대학교 재학생들을 위한 축제 웹 플랫폼입니다. 실시간 이벤트 참여, 경품 추첨, 부스 관리 기능 등을 제공하며, FastAPI와 SQLite 기반으로 경량 백엔드 구조를 설계하였습니다.

3. 주요 기능
🎪 부스 체크인: 학생증(ID) 인증을 통해 참여 인증 도장 받기
🧾 경품 응모 시스템: 참여 횟수 기반 실시간 추첨
📊 실시간 당첨자 공개 (WebSocket 기반)
🛠 관리자 페이지: 부스 도장 승인 및 추첨 제어 기능

4. 기술 스택
백엔드: FastAPI, SQLite, WebSocket
프론트엔드: HTML, JavaScript (Vanilla/HTMX 등), Jinja2 Templates
배포: uvicorn, nginx (선택 사항)
기타: Cookie 기반 인증, 경량 세션 관리
