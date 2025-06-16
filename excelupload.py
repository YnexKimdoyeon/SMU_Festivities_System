import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

# DB 연결
engine = create_engine("sqlite:///student_fees.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 테이블 정의
class StudentFeeDB(Base):
    __tablename__ = "student_fees"
    id = Column(Integer, primary_key=True, index=True)
    studentId = Column(String, unique=True, index=True)
    name = Column(String)
    department = Column(String)

Base.metadata.create_all(bind=engine)

# 엑셀 불러오기
df = pd.read_excel("학생회비납부.xls")

# DB에 추가
session = SessionLocal()
for _, row in df.iterrows():
    entry = StudentFeeDB(
        studentId=str(row['학번']),
        name=row['성명'],
        department=row['학과']
    )
    session.add(entry)
session.commit()
session.close()

print("업로드 완료!")
