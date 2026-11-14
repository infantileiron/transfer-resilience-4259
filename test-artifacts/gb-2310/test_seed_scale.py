import sys
sys.path.insert(0, "/workspace/backend")
from src.services.timeflow import TimeExpandedFlow, ceil_hours

# 复刻种子数据的 22 条弧（停用 e13）
raw = [("S", "A", 8, 6), ("S", "B", 6, 9), ("A", "C", 5, 4), ("A", "D", 5, 5),
       ("B", "D", 5, 3), ("B", "E", 4, 5), ("C", "F", 5, 7), ("D", "F", 4, 4),
       ("D", "G", 5, 6), ("E", "G", 4, 3), ("F", "H", 6, 5), ("G", "H", 6, 4),
       ("H", "T", 10, 6), ("F", "T", 3, 12), ("G", "T", 3, 10), ("A", "B", 2, 2),
       ("D", "E", 2, 2), ("C", "D", 2, 1), ("S", "A", 3, 7), ("D", "A", 2, 3),
       ("H", "G", 1, 5), ("B", "A", 1, 4)]
arcs = [{"arc_id": f"e{i:02}", "source": u, "target": v, "capacity": c, "travel_minutes": m}
        for i, (u, v, c, m) in enumerate(raw, 1)]
nodes = ["S", "A", "B", "C", "D", "E", "F", "G", "H", "T"]
disabled = {"e13"}
transfer = [n for n in nodes if n not in ("S", "T")]
stock = {n: 40 for n in transfer}

import time
t0 = time.time()
f = TimeExpandedFlow(nodes, arcs, "S", "T", disabled, stock, total_cargo=120, deadline_hours=24)
f.run_to_deadline()
elapsed = time.time() - t0
print("max_delivered:", f.value, "/ 120  用时 %.3fs" % elapsed)
print("residual edges:", len(f.residual), " vertices:", len(f.adjacency))
print("checks:", f.checks())
assert all(f.checks().values())
# 逐小时送达单调不减，且不超过货量
cum = 0
for r in [{"h": h, "d": f.delivered_at_hour(h)} for h in range(25)]:
 cum += r["d"]
 assert 0 <= r["d"]
assert cum == f.value <= 120
# 库存全部不超上限
for r in f.inventory_table():
 assert 0 <= r["inventory"] <= stock.get(r["node_id"], 10 ** 12)
# 对账全守恒
assert all(r["conserved"] for r in f.node_reconciliation())
# 停用边 e13 无发运
assert all(r["arc_id"] != "e13" for r in f.shipments_table())
# 72 小时上限的性能
t0 = time.time()
f72 = TimeExpandedFlow(nodes, arcs, "S", "T", disabled, stock, 10 ** 6, 72)
f72.run_to_deadline()
print("72h delivered:", f72.value, " 用时 %.3fs" % (time.time() - t0),
      " residual edges:", len(f72.residual))
assert all(f72.checks().values())
# 检查点恢复在大网络上仍一致
snap = None
part = TimeExpandedFlow(nodes, arcs, "S", "T", disabled, stock, 120, 24)
part.run_to_deadline(on_checkpoint=lambda h, e: None)
snap = part.to_checkpoint()
restored = TimeExpandedFlow.from_checkpoint(snap, nodes, arcs, "S", "T", disabled, stock, 120, 24)
assert restored.built_hours == 24 and restored.value == part.value
print("\nSEED-SCALE END2END OK")
