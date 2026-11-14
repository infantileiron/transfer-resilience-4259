from sqlalchemy import String,Integer,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class ShipmentAnalysis(Base):
 __tablename__="shipment_analyses"
 # 限时发运分析：复用已完成推演锁定的同一份停边快照，独立成表，不改写原推演
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 run_id:Mapped[str]=mapped_column(ForeignKey("network_runs.id"))
 name:Mapped[str]=mapped_column(String(160),unique=True)
 status:Mapped[str]=mapped_column(String(30))
 # 输入参数
 total_cargo:Mapped[int]=mapped_column(Integer)
 deadline_hours:Mapped[int]=mapped_column(Integer)
 stock_limits:Mapped[dict]=mapped_column(JSON)
 # 计算结果与中断恢复检查点（半成品不向前端暴露，仅完成后可读 result）
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 checkpoint:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default="")
 created_at:Mapped[str]=mapped_column(String(64))
 updated_at:Mapped[str]=mapped_column(String(64))
