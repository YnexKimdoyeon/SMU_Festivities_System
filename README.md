# Sunmoon University Festival Web Platform
선문대 축제를 위한 웹사이트

---

## 프로젝트 개요

Sunmoon University Festival Web Platform은 선문대학교 재학생을 위한 축제 웹 플랫폼입니다.  
실시간 이벤트 참여, 경품 추첨, 부스 관리 기능 등을 제공하며, FastAPI와 SQLite 기반으로 경량 백엔드 구조를 설계하였습니다.

---

## 주요 기능

- 🎪 부스 체크인  
  학생증(ID) 인증을 통해 참여 인증 도장을 받습니다.

- 🧾 경품 응모 시스템  
  부스 참여 횟수를 기반으로 실시간 경품 추첨에 자동 응모됩니다.

- 📊 실시간 당첨자 공개  
  WebSocket 기반으로 실시간으로 당첨 결과를 웹에서 확인할 수 있습니다.

- 🛠 관리자 페이지  
  부스 도장 승인, 경품 추첨 제어 등 축제 운영 기능을 제공합니다.

---

## 기술 스택

- 백엔드: FastAPI, SQLite, WebSocket  
- 프론트엔드: HTML, JavaScript (Vanilla / HTMX), Jinja2 Templates  
- 배포: uvicorn, nginx (선택 사항)  
- 기타: Cookie 기반 인증, 경량 세션 관리

---

선문대학교 축제때 실사용하여 /학생회비 납부 확인 자동화/학과별 랭킹/경품자 추첨 자동화/
를 성공적으로 구현하고 테스트 했습니다.

