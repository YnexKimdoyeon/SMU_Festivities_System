import os
from datetime import datetime
from urllib.parse import quote
from fastapi import Body

from fastapi import FastAPI, HTTPException, Depends, Query, Cookie
from pydantic import BaseModel
from typing import List
from collections import Counter
from sqlalchemy import create_engine, Column, Integer, String, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.staticfiles import StaticFiles
import random
from fastapi import Request, Response, HTTPException, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.responses import HTMLResponse
from sqlalchemy import Boolean
from sqlalchemy import or_

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- 복권 DB 연결 ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./lottolist.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

FEE_DB_URL = "sqlite:///./student_fees.db"
fee_engine = create_engine(FEE_DB_URL, connect_args={"check_same_thread": False})
FeeBase = declarative_base()
FeeSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=fee_engine)

# --- 학생 DB 연결 ---
STUDENT_DB_URL = "sqlite:///./students.db"
student_engine = create_engine(STUDENT_DB_URL, connect_args={"check_same_thread": False})
StudentBase = declarative_base()
StudentSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=student_engine)


connected_clients = []

def load_allowed_ips():
    path = os.path.join("static", "allowed_ips.txt")
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def is_ip_allowed(request: Request) -> bool:
    client_ip = request.client.host
    allowed_ips = load_allowed_ips()
    return client_ip in allowed_ips

class LottoEntryDB(Base):
    __tablename__ = "lotto_entries"
    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(String, index=True)
    name = Column(String, index=True)
    department = Column(String)
    numbers = Column(String)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

Base.metadata.create_all(bind=engine)


class StudentDB(StudentBase):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(String, unique=True, index=True)
    name = Column(String)
    department = Column(String)

StudentBase.metadata.create_all(bind=student_engine)

# --- Pydantic Models ---
class LottoEntry(BaseModel):
    studentId: str
    name: str
    department: str
    numbers: List[List[str]]

class CheckNumber(BaseModel):
    numbers: List[str]

# --- DB 의존성 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_student_db():
    db = StudentSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_fee_db():
    db = FeeSessionLocal()
    try:
        yield db
    finally:
        db.close()


CHECKBOX_FIELDS = ["학생증 확인", "본인확인", "현장확인","청춘복권"]



FeeBase.metadata.create_all(bind=fee_engine)

class StudentFeeDB(FeeBase):
    __tablename__ = "student_fees"
    studentId = Column(String, primary_key=True, index=True)
    name = Column(String)
    department = Column(String)
    check_idcard = Column(Boolean, default=False)  # 학생증 확인
    check_identity = Column(Boolean, default=False)  # 본인확인
FeeBase.metadata.create_all(bind=fee_engine)


class StudentInput(BaseModel):
    studentId: str
    name: str
    department: str

# --- API Routes ---

async def broadcast_refresh():
    for ws in connected_clients:
        try:
            await ws.send_json({"type": "refresh"})
        except:
            pass
@app.post("/fee-login")
async def fee_login(request: Request):
    data = await request.json()
    name = data.get("name")
    password = data.get("password")

    if password != "chdgkrtodghl" or not name:
        raise HTTPException(status_code=401, detail="인증 실패")

    from starlette.responses import JSONResponse
    response = JSONResponse(content={"message": "성공"})

    # ✅ 한글 이름은 URL 인코딩 후 쿠키 저장
    encoded_name = quote(name)  # e.g., 김도연 → %EA%B9%80%EB%8F%84%EC%97%B0
    response.set_cookie("fee_auth", "true", httponly=True)
    response.set_cookie("username", encoded_name, httponly=False)

    return response
@app.post("/api/fee")
async def add_fee(entry: StudentInput, db: Session = Depends(get_fee_db)):
    existing = db.query(StudentFeeDB).filter(StudentFeeDB.studentId == entry.studentId).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 학번입니다.")

    db_entry = StudentFeeDB(
        studentId=entry.studentId,
        name=entry.name,
        department=entry.department
    )
    db.add(db_entry)
    db.commit()

    # ✅ 비동기로 브로드캐스트
    await broadcast_refresh()

    return {"message": "납부자가 등록되었습니다."}

# --- API 엔드포인트 ---
@app.get("/api/fee-list")
def get_fee_list(db: Session = Depends(get_fee_db)):
    entries = db.query(StudentFeeDB).all()
    return {
        "entries": [
            {
                "studentId": entry.studentId,
                "name": entry.name,
                "department": entry.department,
                "check_idcard": entry.check_idcard,
                "check_identity": entry.check_identity
            } for entry in entries
        ]
    }
@app.post("/api/student")
def add_student(entry: StudentInput, db: Session = Depends(get_student_db)):
    if len(entry.studentId) != 10 or not entry.studentId.isdigit():
        raise HTTPException(status_code=400, detail="학번은 숫자 10자리여야 합니다.")

    existing = db.query(StudentDB).filter(StudentDB.studentId == entry.studentId).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 학번입니다.")

    db_student = StudentDB(
        studentId=entry.studentId,
        name=entry.name,
        department=entry.department
    )
    db.add(db_student)
    db.commit()
    return {"message": "학생 정보가 등록되었습니다."}

@app.post("/api/issue")
def issue_lotto(entry: LottoEntry, db: Session = Depends(get_db)):
    if not entry.numbers or not all(isinstance(ns, list) and len(ns) == 5 for ns in entry.numbers):
        raise HTTPException(status_code=400, detail="각 로또 번호 세트는 5자리여야 합니다.")

    if len(entry.studentId) != 10:
        raise HTTPException(status_code=400, detail="학번은 정확히 10자리여야 합니다.")

    existing = db.query(LottoEntryDB).filter(LottoEntryDB.studentId == entry.studentId).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 해당 학번으로 청춘복권이 발급되었습니다.")

    now = datetime.now().isoformat()
    for number_set in entry.numbers:
        if len(set(number_set)) != 5 or not all(v.isdigit() and len(v) == 1 for v in number_set):
            raise HTTPException(status_code=400, detail="번호 세트는 중복 없는 1자리 숫자 5개여야 합니다.")
        db_entry = LottoEntryDB(
            studentId=entry.studentId,
            name=entry.name,
            department=entry.department,
            numbers=' '.join(number_set),
            created_at=now
        )
        db.add(db_entry)
    db.commit()
    return {"message": f"{len(entry.numbers)}개의 로또 번호가 발급되었습니다."}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    entries = db.query(LottoEntryDB).all()
    counter = Counter(entry.numbers for entry in entries)
    for entry in entries:
        counter.update(entry.numbers.split())
    sorted_stats = sorted(counter.items(), key=lambda x: -x[1])
    return {"stats": sorted_stats}

@app.post("/api/match")
def match_count(check: CheckNumber, db: Session = Depends(get_db)):
    if len(check.numbers) != 5:
        raise HTTPException(status_code=400, detail="번호는 5자리여야 합니다.")
    target = ' '.join(check.numbers)
    count = db.query(LottoEntryDB).filter(LottoEntryDB.numbers == target).count()
    return {"count": count}

@app.get("/api/my-lotto")
def get_my_lotto(studentId: str = Query(...), db: Session = Depends(get_db)):
    entries = db.query(LottoEntryDB).filter(LottoEntryDB.studentId == studentId).all()
    if not entries:
        return {"entries": []}
    return {
        "entries": [
            {
                "numbers": entry.numbers,
                "created_at": entry.created_at,
                "department": entry.department,
                "name": entry.name
            } for entry in entries
        ]
    }

@app.get("/api/winner")
def get_random_winner(db: Session = Depends(get_db)):
    all_entries = db.query(LottoEntryDB).all()
    if not all_entries:
        raise HTTPException(status_code=404, detail="당첨자가 없습니다.")
    selected_entry = random.choice(all_entries)
    winning_numbers = selected_entry.numbers
    winners = db.query(LottoEntryDB).filter(LottoEntryDB.numbers == winning_numbers).all()
    return {
        "numbers": winning_numbers.split(),
        "winners": [
            {
                "name": winner.name,
                "department": winner.department,
                "studentId": winner.studentId
            } for winner in winners
        ]
    }

@app.post("/auth")
async def auth(request: Request, response: Response):
    data = await request.json()
    if data.get("password") == "2021243016":
        response = RedirectResponse(url="/student-list", status_code=302)
        response.set_cookie("auth", "true", httponly=True)
        return response
    raise HTTPException(status_code=401, detail="비밀번호 틀림")

@app.get("/auth/check")
def auth_check(auth: str = Cookie(default=None)):
    return {"authenticated": auth == "true"}

@app.get("/api/list")
def get_combined_list(
    source: str = Query(..., description="student 또는 lotto"),
    db: Session = Depends(get_db),
    student_db: Session = Depends(get_student_db)
):
    if source == "student":
        entries = student_db.query(StudentDB).all()
        result = [
            {
                "name": entry.name,
                "department": entry.department,
                "studentId": entry.studentId
            } for entry in entries
        ]
    elif source == "lotto":
        entries = db.query(LottoEntryDB).all()
        result = [
            {
                "id": entry.id,
                "name": entry.name,
                "department": entry.department,
                "studentId": entry.studentId,
                "numbers": entry.numbers,
                "created_at": entry.created_at
            } for entry in entries
        ]
    else:
        raise HTTPException(status_code=400, detail="올바른 source 값을 지정해주세요. (student 또는 lotto)")

    return {"entries": result}


@app.get("/api/ranking")
def get_department_ranking(student_db: Session = Depends(get_student_db)):
    quota_map = departments = {
    "AI소프트웨어학과": 179,
    "IT경영학과": 155,
    "간호학과": 375,
    "건설시스템안전공학과": 52,
    "건축사회환경공학부": 13,
    "건축학부": 332,
    "경영학과": 399,
    "국어국문학과": 48,
    "국제경제통상학과": 65,
    "국제관계학과": 57,
    "국제레저관광학과": 2,
    "글로벌경영학과": 3,
    "글로벌경제학과": 116,
    "글로벌관광학과": 92,
    "글로벌관광학부": 125,
    "글로벌소프트웨어학과": 1,
    "글로벌인재학부": 143,
    "글로벌자유전공학부": 93,
    "글로벌한국어교육학과": 42,
    "글로벌한국학과": 99,
    "기계ICT융합공학부": 42,
    "기계공학과": 225,
    "디스플레이반도체공학과": 134,
    "디자인학부": 154,
    "디지털콘텐츠학부": 31,
    "무도경호학과": 27,
    "무도경호학부": 31,
    "무도학부": 91,
    "물리치료학과": 203,
    "미디어커뮤니케이션학과": 32,
    "미디어커뮤니케이션학부": 310,
    "미래자동차공학부": 182,
    "반도체소재공학과": 43,
    "법·경찰학과": 226,
    "사학과": 59,
    "사회복지학과": 202,
    "산업경영공학과": 69,
    "산업안전경영공학과": 91,
    "상담·산업심리학과": 61,
    "상담산업심리학과": 2,
    "상담심리사회복지학과": 18,
    "상담심리학과": 140,
    "소방방재안전학과": 45,
    "수산생명의학과": 149,
    "스마트자동차공학부": 41,
    "스마트정보통신공학과": 119,
    "스포츠과학과": 52,
    "스포츠과학부": 198,
    "시각디자인학과": 61,
    "식품공학·영양학부": 52,
    "식품과학부": 137,
    "신소재공학과": 99,
    "신학과": 190,
    "신학순결학과": 1,
    "에너지화학공학과": 57,
    "역사·영상콘텐츠학부": 53,
    "역사문화콘텐츠학과": 10,
    "역사문화콘텐츠학부": 13,
    "영상예술학과": 78,
    "영화영상학과": 36,
    "외국어자율전공학부": 166,
    "외국어학부": 403,
    "응급구조학과": 154,
    "일어일본학과": 1,
    "자유전공학부": 109,
    "전자공학과": 235,
    "정보통신공학과": 48,
    "정치·국제학과": 30,
    "제약생명공학과": 178,
    "제약화장품학과": 45,
    "치위생학과": 176,
    "컴퓨터공학부": 559,
    "한국문학콘텐츠창작학과": 14,
    "항공관광학부": 32,
    "행정·공기업학과": 90,
    "행정학과": 2,
    "행정학과(야)": 1,
    "환경생명화학공학과": 38
}

    # ✅ 참여자수: students.db 기준 (실제 등록된 학생 수)
    participation = (
        student_db.query(StudentDB.department, func.count().label("count"))
        .group_by(StudentDB.department)
        .all()
    )

    ranking = []
    for dept, count in participation:
        total = quota_map.get(dept)
        if total:
            rate = round(count / total * 100, 2)
            ranking.append({
                "학과": dept,
                "참여자수": count,
                "총원": total,
                "참여율": rate
            })

    sorted_ranking = sorted(ranking, key=lambda x: x["참여율"], reverse=True)
    return {
        "top5": sorted_ranking[:5],
        "full": sorted_ranking
    }
@app.get("/", response_class=HTMLResponse)
async def read_main():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/lottery", response_class=HTMLResponse)
async def read_lottery():
    with open("static/lottery.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/ranking", response_class=HTMLResponse)
async def read_ranking():
    with open("static/ranking.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/admin", response_class=HTMLResponse)
async def read_admin(request: Request):
    if not is_ip_allowed(request):
        return HTMLResponse(content="접근이 허용되지 않은 IP입니다.", status_code=403)
    with open("static/lotto_admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/winner", response_class=HTMLResponse)
async def read_winner(request: Request):
    if not is_ip_allowed(request):
        return HTMLResponse(content="접근이 허용되지 않은 IP입니다.", status_code=403)
    with open("static/winner.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/register", response_class=HTMLResponse)
async def student_register_page(request: Request):
    if not is_ip_allowed(request):
        return HTMLResponse(content="접근이 허용되지 않은 IP입니다.", status_code=403)
    with open("static/student_register.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/student-list", response_class=HTMLResponse)
async def student_list_page(request: Request, auth: str = Cookie(None)):
    if not is_ip_allowed(request):
        return HTMLResponse(content="접근이 허용되지 않은 IP입니다.", status_code=403)

    if auth != "true":
        with open("static/login.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    with open("static/student_list.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/fee-list", response_class=HTMLResponse)
async def fee_list_page():
    with open("static/fee_list.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/fee-search")
def fee_search(q: str = "", db: Session = Depends(get_fee_db)):
    keyword = f"%{q}%"
    results = db.query(StudentFeeDB).filter(
        or_(
            StudentFeeDB.studentId.like(keyword),
            StudentFeeDB.name.like(keyword),
            StudentFeeDB.department.like(keyword)
        )
    ).all()
    return {
        "entries": [
            {
                "studentId": r.studentId,
                "name": r.name,
                "department": r.department,
                "check_idcard": r.check_idcard,
                "check_identity": r.check_identity
            }
            for r in results
        ]
    }
@app.patch("/api/fee-check")
def update_fee_check(
    studentId: str = Body(...),
    field: str = Body(...),
    value: bool = Body(...),
    db: Session = Depends(get_fee_db)
):
    entry = db.query(StudentFeeDB).filter(StudentFeeDB.studentId == studentId).first()
    if not entry:
        raise HTTPException(status_code=404, detail="해당 학번이 존재하지 않습니다.")

    if field not in ["check_idcard", "check_identity"]:
        raise HTTPException(status_code=400, detail="올바르지 않은 필드입니다.")

    setattr(entry, field, value)
    db.commit()
    return {"message": "상태가 업데이트되었습니다."}


@app.get("/extra-register", response_class=HTMLResponse)
async def extra_register_page():
    with open("static/extra_register.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/extra-list", response_class=HTMLResponse)
async def extra_list_page():
    with open("static/extra_list.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/extra-list")
def get_extra_list(db: Session = Depends(get_fee_db)):
    entries = db.query(StudentExtraDB).all()
    return {
        "entries": [
            {
                "studentId": e.studentId,
                "name": e.name,
                "phone": e.phone,
                "bank_account": e.bank_account,
                "agree_privacy": e.agree_privacy,
                "agree_marketing": e.agree_marketing,
                "return_mat": e.return_mat
            } for e in entries
        ]
    }


from pydantic import BaseModel

class ExtraInput(BaseModel):
    studentId: str
    name: str
    phone: str
    bank_account: str
    agree_privacy: bool = False
    agree_marketing: bool = False

class StudentExtraDB(FeeBase):
    __tablename__ = "student_extra"
    studentId = Column(String, primary_key=True)
    name = Column(String)
    phone = Column(String)
    bank_account = Column(String)
    agree_privacy = Column(Boolean, default=False)
    agree_marketing = Column(Boolean, default=False)
    return_mat = Column(Boolean, default=False)  # ✅ 돗자리 반환 여부
FeeBase.metadata.create_all(bind=fee_engine)

@app.patch("/api/extra-update-return")
def update_return_mat(
        studentId: str = Body(...),
        return_mat: bool = Body(...),
        db: Session = Depends(get_fee_db)
):
    entry = db.query(StudentExtraDB).filter(StudentExtraDB.studentId == studentId).first()
    if not entry:
        raise HTTPException(status_code=404, detail="대상 학번을 찾을 수 없습니다.")

    entry.return_mat = return_mat
    db.commit()
    return {"message": "돗자리 반환 상태가 업데이트되었습니다."}
@app.post("/api/extra-register")
def register_extra(entry: ExtraInput, db: Session = Depends(get_fee_db)):
    # StudentFeeDB에 학번과 이름 일치하는지 확인
    match = db.query(StudentFeeDB).filter(
        StudentFeeDB.studentId == entry.studentId,
        StudentFeeDB.name == entry.name
    ).first()

    if not match:
        raise HTTPException(status_code=404, detail="학생회비 DB에 등록되지 않은 사용자입니다.")

    # 이미 등록된 경우 막기
    if db.query(StudentExtraDB).filter(StudentExtraDB.studentId == entry.studentId).first():
        raise HTTPException(status_code=400, detail="이미 돗자리 빌리기 정보가 등록되었습니다.")

    new_entry = StudentExtraDB(
        studentId=entry.studentId,
        name=entry.name,
        phone=entry.phone,
        bank_account=entry.bank_account,
        agree_privacy=entry.agree_privacy,
        agree_marketing=entry.agree_marketing
    )
    db.add(new_entry)
    db.commit()
    return {"message": "추가 정보가 등록되었습니다."}