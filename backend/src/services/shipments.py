import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from src.models import ShipmentAnalysis, NetworkRun, OutageScenario, NetworkDataset
from src.services.timeflow import TimeExpandedFlow, ceil_hours
from src.config.settings import REDIS_URL
from src.utils.time import now
from src.utils.serialization import serialize

SHIPMENT_QUEUE = "transfer-resilience:shipment-jobs"


def require_completed_run(db, run_id):
 run = db.get(NetworkRun, run_id)
 if not run:
  raise HTTPException(404, "推演不存在")
 if run.status != "completed":
  raise HTTPException(409, "仅限时发运分析需要基于已完成的推演")
 return run


def _engine_inputs(db, run):
 scenario = db.get(OutageScenario, run.scenario_id)
 dataset = db.get(NetworkDataset, scenario.dataset_id)
 node_ids = [n["node_id"] for n in dataset.nodes]
 # 沿用当次停边快照：与原推演完全相同的弧、容量、时长、停用集合
 return node_ids, scenario.arc_snapshot, scenario.source_node, scenario.sink_node, \
     list(scenario.disabled_arc_ids), dataset, scenario


def create(db, payload, user):
 run = require_completed_run(db, run_id=payload.run_id)
 node_ids, arcs, source, sink, disabled, dataset, scenario = _engine_inputs(db, run)
 # 中转站 = 除源/汇外的全部节点，库存上限必须逐站填写，缺一项即拒绝
 transfer_nodes = [n for n in node_ids if n not in (source, sink)]
 missing = [n for n in transfer_nodes if n not in payload.stock_limits]
 if missing:
  raise HTTPException(422, "缺少中转站库存上限：" + "、".join(missing))
 unknown = [n for n in payload.stock_limits if n not in transfer_nodes]
 if unknown:
  raise HTTPException(422, "库存上限只能填写中转站（源/汇不限）：" + "、".join(unknown))
 if db.scalar(select(ShipmentAnalysis).where(ShipmentAnalysis.name == payload.name)):
  raise HTTPException(409, "限时发运分析名称已存在")
 item = ShipmentAnalysis(
  id=str(uuid.uuid4()), run_id=run.id, name=payload.name, status="queued",
  total_cargo=payload.total_cargo, deadline_hours=payload.deadline_hours,
  stock_limits=payload.stock_limits, result={}, checkpoint={}, error="",
  created_at=now(), updated_at=now())
 db.add(item)
 db.commit()
 try:
  import redis
  redis.Redis.from_url(REDIS_URL).lpush(SHIPMENT_QUEUE, item.id)
 except Exception:
  item.status = "failed"
  item.error = "后台队列不可用，请重试"
  db.commit()
  raise HTTPException(503, item.error)
 return serialize(item)


def _build_engine(db, item):
 run = db.get(NetworkRun, item.run_id)
 node_ids, arcs, source, sink, disabled, _, _ = _engine_inputs(db, run)
 kwargs = dict(node_ids=node_ids, arcs=arcs, source=source, sink=sink,
               disabled=disabled, stock_caps=dict(item.stock_limits),
               total_cargo=item.total_cargo, deadline_hours=item.deadline_hours)
 # 从中断检查点恢复；无检查点则从头开始
 if item.checkpoint and item.checkpoint.get("built_hours", -1) >= 0:
  return TimeExpandedFlow.from_checkpoint(item.checkpoint, **kwargs), kwargs
 return TimeExpandedFlow(**kwargs), kwargs


def execute(db, item_id):
 item = db.get(ShipmentAnalysis, item_id)
 if not item or item.status not in ("queued", "running"):
  return
 item.status = "running"
 item.updated_at = now()
 db.commit()
 try:
  engine, kwargs = _build_engine(db, item)
  # 每完成一个小时层就提交检查点；中断后重启从最后已保存时点继续，不重算
  def save_checkpoint(hour, eng):
   item.checkpoint = eng.to_checkpoint()
   item.updated_at = now()
   db.commit()
  engine.run_to_deadline(on_checkpoint=save_checkpoint)
  item.result = _assemble_result(db, item, engine)
  item.status = "completed"
  item.checkpoint = {}  # 完成后清理检查点，只保留完整结果
  item.updated_at = now()
  db.commit()
 except Exception as e:
  item.error = str(e)
  item.status = "failed"
  item.updated_at = now()
  db.commit()
  raise


def _assemble_result(db, item, engine):
 run = db.get(NetworkRun, item.run_id)
 node_ids, arcs, source, sink, disabled, dataset, scenario = _engine_inputs(db, run)
 checks = engine.checks()
 if not all(checks.values()):
  raise ValueError("限时发运证据检查失败，未输出可信结论")
 shipments = engine.shipments_table()
 inventory = engine.inventory_table()
 reconciliation = engine.node_reconciliation()
 delivered_series = []
 for h in range(item.deadline_hours + 1):
  delivered_series.append({"hour": h, "newly_delivered": engine.delivered_at_hour(h)})
 cumulative = 0
 for row in delivered_series:
  cumulative += row["newly_delivered"]
  row["cumulative_delivered"] = cumulative
 digest_base = {"run_id": item.run_id, "total_cargo": item.total_cargo,
                "deadline_hours": item.deadline_hours,
                "stock_limits": item.stock_limits,
                "snapshot_checksum": run.result.get("checksum", "")}
 return {
  "run_id": item.run_id,
  "scenario_id": scenario.id,
  "dataset_id": dataset.id,
  "nodes": dataset.nodes,
  "arcs": arcs,
  "source": source,
  "sink": sink,
  "disabled_arc_ids": disabled,
  "total_cargo": item.total_cargo,
  "deadline_hours": item.deadline_hours,
  "stock_limits": item.stock_limits,
  "max_delivered": engine.value,
  "undelivered": item.total_cargo - engine.value,
  "delivered_series": delivered_series,
  "shipments": shipments,
  "inventory": inventory,
  "reconciliation": reconciliation,
  "checks": checks,
  "arc_lead_hours": [{"arc_id": a["arc_id"], "lead_hours": ceil_hours(a["travel_minutes"])}
                     for a in engine.arcs],
  "checksum": hashlib.sha256(
   json.dumps(digest_base, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
  "assumptions": [
   "沿用已完成推演锁定的同一份停边快照：边容量按箱/小时、时长按分钟，停用边与零容量边不参与发运。",
   "每整点发一班车，单班容量沿用该边每小时箱量；行程分钟向上取整到小时，零时长边可在同一小时当场转运。",
   "货物可在站内等待但不可提前到达；截止小时之后到达的班次不进入网络，送达量只统计不晚于截止的到达。",
   "每个中转站设站内库存上限，节点拆分后当场转运与等待一并受上限约束；源站与汇站不设库存上限。",
   "时间展开网络上用 Edmonds–Karp 求最多送达量，逐小时逐边发运、站内库存和按节点收发库存对账均输出整数证据。",
   "整箱货量在第 0 小时一次性投放，受网络瓶颈未投放的部分在源节点对账为未投放，不计入任何站内库存。"]}
