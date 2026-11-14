import sys
import types
import importlib.util
sys.path.insert(0, "/workspace/backend")

# 注入外部依赖 stub，使 shipments 模块可在无第三方库环境导入
def stub(name, **attrs):
 mod = types.ModuleType(name)
 for k, v in attrs.items():
  setattr(mod, k, v)
 sys.modules[name] = mod
 return mod

class HTTPException(Exception):
 def __init__(self, status, detail):
  self.status_code = status
  self.detail = detail
fastapi = stub("fastapi", HTTPException=HTTPException)
sqla = stub("sqlalchemy", select=lambda *a, **k: None)
orm = stub("sqlalchemy.orm")
orm.Mapped = object
orm.mapped_column = lambda *a, **k: None
stub("sqlalchemy.orm", Mapped=object, mapped_column=lambda *a, **k: None)

# src.config.database / settings / models / utils 的最小 stub
dbmod = stub("src.config.database", Base=object, Session=None, engine=None, db_session=None)
stub("src.config.settings", REDIS_URL="redis://localhost", DATABASE_URL="sqlite://",
     JWT_SECRET="x", SEED_DEMO=False)
models = stub("src.models")
class _M:
 def __init__(self, **kw): self.__dict__.update(kw)
models.ShipmentAnalysis = _M
models.NetworkRun = _M
models.OutageScenario = _M
models.NetworkDataset = _M
stub("src.utils.time", now=lambda: "2026-11-14T00:00:00+00:00")
stub("src.utils.serialization", serialize=lambda o: o.__dict__)

# 现在直接按文件路径加载 shipments（其包内相对导入已被上面的 stub 覆盖）
# 改用包路径导入，确保 src.services.timeflow 走真实代码
spec = importlib.util.spec_from_file_location(
 "src.services.shipments", "/workspace/backend/src/services/shipments.py")
svc = importlib.util.module_from_spec(spec)
sys.modules["src.services.shipments"] = svc
spec.loader.exec_module(svc)
from src.services.timeflow import TimeExpandedFlow

raw = [("S", "A", 8, 6), ("S", "B", 6, 9), ("A", "C", 5, 4), ("A", "D", 5, 5),
       ("B", "D", 5, 3), ("B", "E", 4, 5), ("C", "F", 5, 7), ("D", "F", 4, 4),
       ("D", "G", 5, 6), ("E", "G", 4, 3), ("F", "H", 6, 5), ("G", "H", 6, 4),
       ("H", "T", 10, 6), ("F", "T", 3, 12), ("G", "T", 3, 10), ("A", "B", 2, 2),
       ("D", "E", 2, 2), ("C", "D", 2, 1), ("S", "A", 3, 7), ("D", "A", 2, 3),
       ("H", "G", 1, 5), ("B", "A", 1, 4)]
arcs = [{"arc_id": f"e{i:02}", "source": u, "target": v, "capacity": c, "travel_minutes": m}
        for i, (u, v, c, m) in enumerate(raw, 1)]
node_ids = ["S", "A", "B", "C", "D", "E", "F", "G", "H", "T"]
nodes = [{"node_id": x} for x in node_ids]
disabled = ["e13"]


class FakeRun:
 id = "run-1"
 status = "completed"
 scenario_id = "sc-1"
 result = {"checksum": "abc123"}


class FakeScenario:
 id = "sc-1"
 dataset_id = "ds-1"
 arc_snapshot = arcs
 source_node = "S"
 sink_node = "T"
 disabled_arc_ids = disabled


class FakeDataset:
 id = "ds-1"
 nodes = nodes


class FakeItem:
 def __init__(self):
  self.id = "ship-1"
  self.run_id = "run-1"
  self.name = "test"
  self.status = "running"
  self.total_cargo = 120
  self.deadline_hours = 24
  self.stock_limits = {n: 40 for n in node_ids if n not in ("S", "T")}
  self.result = {}
  self.checkpoint = {}
  self.error = ""
  self.updated_at = ""


def fake_inputs(db, run):
 return node_ids, arcs, "S", "T", list(disabled), FakeDataset(), FakeScenario()
svc._engine_inputs = fake_inputs


class FakeDB:
 def get(self, model, key):
  return {"run-1": FakeRun(), "sc-1": FakeScenario(), "ds-1": FakeDataset()}.get(key)


db = FakeDB()
item = FakeItem()

# 1. 无检查点从头构建
engine, kwargs = svc._build_engine(db, item)
assert isinstance(engine, TimeExpandedFlow)
engine.run_to_deadline()
full_value = engine.value
full_shipments = engine.shipments_table()

# 2. 第10小时中断 -> 检查点 -> 恢复，结果一致
part = TimeExpandedFlow(**kwargs)
cp10 = {}
part.run_to_deadline(on_checkpoint=lambda h, e: cp10.update(e.to_checkpoint()) if h == 10 else None)
item.checkpoint = cp10
restored, _ = svc._build_engine(db, item)
restored.run_to_deadline()
assert restored.built_hours == 24
assert restored.value == full_value
assert restored.shipments_table() == full_shipments
print("checkpoint resume:", restored.value, "==", full_value)

# 3. 组装结果并核验
result = svc._assemble_result(db, item, restored)
required = ["run_id", "scenario_id", "dataset_id", "nodes", "arcs", "source", "sink",
            "disabled_arc_ids", "total_cargo", "deadline_hours", "stock_limits",
            "max_delivered", "undelivered", "delivered_series", "shipments",
            "inventory", "reconciliation", "checks", "arc_lead_hours", "checksum",
            "assumptions"]
for k in required:
 assert k in result, k
assert result["max_delivered"] == full_value
assert result["undelivered"] == 120 - full_value
assert all(result["checks"].values())
assert len(result["delivered_series"]) == 25
assert result["delivered_series"][-1]["cumulative_delivered"] == full_value
assert all(r["conserved"] for r in result["reconciliation"])
total_end = sum(r["end_inventory"] for r in result["reconciliation"])
unsupp = next(r["unsupplied"] for r in result["reconciliation"] if r["role"] == "source")
assert result["max_delivered"] + total_end + unsupp == 120
assert all(r["arc_id"] != "e13" for r in result["shipments"])
assert all(r["arrive_hour"] <= 24 for r in result["shipments"])
print("max_delivered:", result["max_delivered"], "undelivered:", result["undelivered"])
print("shipment rows:", len(result["shipments"]), "inventory rows:", len(result["inventory"]),
      "recon rows:", len(result["reconciliation"]))
print("\nSERVICE ORCHESTRATION OK")
