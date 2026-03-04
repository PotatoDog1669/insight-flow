from app.db.database import SessionLocal
from app.models.source import Source

db = SessionLocal()
sources = db.query(Source).all()
for s in sources:
    if "X" in s.name or "Social" in s.category:
        print(f"ID: {s.id}, Name: {s.name}, Method: {s.collect_method}, Category: {s.category}")
