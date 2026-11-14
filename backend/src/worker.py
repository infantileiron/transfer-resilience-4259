from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import NetworkRun,OutageScenario,NetworkDataset,ShipmentAnalysis
from src.services.analysis import analyze
from src.services import shipments as shipment_service
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path("/artifacts/worker-heartbeat")
def execute(id):
 with Session() as db:
  run=db.get(NetworkRun,id)
  if not run or run.status not in ("queued","running"):return
  run.status="running";db.commit()
  try:
   scenario=db.get(OutageScenario,run.scenario_id);dataset=db.get(NetworkDataset,scenario.dataset_id)
   run.result=analyze(dataset,scenario);run.status="completed"
  except Exception as e:run.error=str(e);run.status="failed";traceback.print_exc()
  db.commit()
def execute_shipment(id):
 with Session() as db:
  # 检查点已在 service 内逐小时提交；中断重启后从最后已保存时点恢复，不展示半成品
  try:shipment_service.execute(db,id)
  except Exception:traceback.print_exc()
with Session() as db:
 # 启动恢复：原推演与限时发运分析中未完成的任务重新入队，各自从已保存时点继续
 for id in db.scalars(select(NetworkRun.id).where(NetworkRun.status.in_(["queued","running"]))):client.lpush("transfer-resilience:jobs",id)
 for id in db.scalars(select(ShipmentAnalysis.id).where(ShipmentAnalysis.status.in_(["queued","running"]))):client.lpush(shipment_service.SHIPMENT_QUEUE,id)
while True:
 heartbeat.touch()
 # 优先取限时发运队列，再取原推演队列；两路任务互不阻塞
 job=client.brpop(shipment_service.SHIPMENT_QUEUE,timeout=1)
 if job:execute_shipment(job[1].decode());continue
 job=client.brpop("transfer-resilience:jobs",timeout=1)
 if job:execute(job[1].decode())
