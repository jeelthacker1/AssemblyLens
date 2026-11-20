import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, JSON, Integer, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class Record(Base):
    __tablename__='records'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant: Mapped[str]=mapped_column(String(80),index=True)
    kind: Mapped[str]=mapped_column(String(40))
    body: Mapped[dict]=mapped_column(JSON)
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(Index('records_scope','tenant','kind','created'),)
class Inspection(Base):
    __tablename__='inspections'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant: Mapped[str]=mapped_column(String(80))
    serial: Mapped[str]=mapped_column(String(120))
    station: Mapped[str]=mapped_column(String(36))
    workflow: Mapped[dict]=mapped_column(JSON)
    state: Mapped[dict]=mapped_column(JSON)
    version: Mapped[int]=mapped_column(Integer,default=0)
    last_sequence: Mapped[int]=mapped_column(Integer,default=-1)
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('tenant','serial'),Index('inspections_scope','tenant','created'))
class Event(Base):
    __tablename__='events'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant: Mapped[str]=mapped_column(String(80))
    inspection: Mapped[str]=mapped_column(String(36),default='')
    actor: Mapped[str]=mapped_column(String(80))
    action: Mapped[str]=mapped_column(String(80))
    body: Mapped[dict]=mapped_column(JSON)
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(Index('events_scope','tenant','inspection','created'),)

class Outbox(Base):
    __tablename__='outbox'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    body: Mapped[dict]=mapped_column(JSON)
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    delivered: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)

url=os.getenv('DATABASE_URL','sqlite:///./data/assemblylens.db')
os.makedirs('data',exist_ok=True)
engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {},pool_pre_ping=True)
Session=sessionmaker(engine,expire_on_commit=False)
def init(): Base.metadata.create_all(engine)
