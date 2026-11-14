import sys
import types
import importlib.util
sys.path.insert(0, "/workspace/backend")


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


stub("fastapi", HTTPException=HTTPException)
class _Select:
 def where(self, *a): return self
stub("sqlalchemy", select=lambda *a, **k: _Select())
stub("sqlalchemy.orm", Mapped=object, mapped_column=lambda *a, **k: None)
stub("src.config.database", Base=object, Session=None, engine=None, db_session=None)
stub("src.config.settings", REDIS_URL="redis://localhost:0", DATABASE_URL="sqlite://",
     JWT_SECRET="x", SEED_DEMO=False)
models = stub("src.models")
class _M:
 name = "name"
 def __init__(self, **kw): self.__dict__.update(kw)
models.ShipmentAnalysis = _M
models.NetworkRun = _M
models.OutageScenario = _M
models.NetworkDataset = _M
stub("src.utils.time", now=lambda: "2026-11-14T00:00:00+00:00")
stub("src.utils.serialization", serialize=lambda o: o.__dict__)
spec = importlib.util.spec_from_file_location(
 "src.services.shipments", "/workspace/backend/src/services/shipments.py")
svc = importlib.util.module_from_spec(spec)
sys.modules["src.services.shipments"] = svc
spec.loader.exec_module(svc)

node_ids = ["S", "A", "B", "T"]
arcs = [{"arc_id": "e1", "source": "S", "target": "A", "capacity": 5, "travel_minutes": 60},
        {"arc_id": "e2", "source": "A", "target": "T", "capacity": 5, "travel_minutes": 60}]


class Run:
 def __init__(self, status): self.id = "r1"; self.status = status; self.scenario_id = "sc1"


class Scenario:
 id = "sc1"; dataset_id = "ds1"; arc_snapshot = arcs
 source_node = "S"; sink_node = "T"; disabled_arc_ids = []


class Dataset:
 id = "ds1"; nodes = [{"node_id": n} for n in node_ids]


class Payload:
 def __init__(self, **kw):
  self.run_id = "r1"; self.name = "n1"; self.total_cargo = 100
  self.deadline_hours = 24; self.stock_limits = {"A": 10, "B": 10}
  self.__dict__.update(kw)


class DB:
 def __init__(self, run_status="completed", name_taken=False):
  self.run = Run(run_status); self.name_taken = name_taken
 def get(self, model, key):
  if key == "r1": return self.run
  if key == "sc1": return Scenario()
  if key == "ds1": return Dataset()
  return None
 def scalar(self, q): return "taken" if self.name_taken else None
 def add(self, o): pass
 def commit(self): pass


def expect_http(label, db, payload, status):
 try:
  svc.create(db, payload, {"email": "analyst@x"})
  print("  FAIL", label, "(未拒绝)")
  return False
 except HTTPException as e:
  ok = e.status_code == status
  print(("  PASS " if ok else "  FAIL ") + label, "->", e.status_code, e.detail)
  return ok


results = []
# 1. 推演不存在
db_missing = DB()
db_missing.get = lambda model, key: None
results.append(expect_http("推演不存在 404", db_missing, Payload(), 404))
# 2. 推演未完成
results.append(expect_http("推演未完成 409", DB(run_status="queued"), Payload(), 409))
# 3. 缺中转站库存上限
results.append(expect_http("缺B库存上限 422", DB(), Payload(stock_limits={"A": 10}), 422))
# 4. 给源站填了上限（源/汇不允许）
results.append(expect_http("源站填上限 422", DB(),
                           Payload(stock_limits={"A": 10, "B": 10, "S": 5}), 422))
# 5. 重名
results.append(expect_http("名称重复 409", DB(name_taken=True), Payload(), 409))
# 6. 队列不可用 -> 503（REDIS_URL 指向不可达端口）
try:
 svc.create(DB(), Payload(name="unique-1"), {"email": "analyst@x"})
 results.append(False); print("  FAIL 队列不可用未拒绝")
except HTTPException as e:
 ok = e.status_code == 503
 results.append(ok); print(("  PASS " if ok else "  FAIL "), "队列不可用 503 ->", e.status_code)

print("\n%d/%d validation checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
