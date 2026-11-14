import sys
sys.path.insert(0, "/workspace/backend")
from src.services.timeflow import TimeExpandedFlow

# 瓶颈在出站：源站每小时只能发2，但先投放10 -> 源站产生站内等待库存
arcs = [{"arc_id": "e1", "source": "S", "target": "T", "capacity": 2, "travel_minutes": 60}]
f = TimeExpandedFlow(["S", "T"], arcs, "S", "T", set(), {}, total_cargo=10, deadline_hours=3)
f.run_to_deadline()
print("value (h0,h1,h2 各2 -> 6):", f.value)
assert f.value == 6
# 截止3：h0发2到T@1, h1发2到T@2, h2发2到T@3 = 6；末层S库存= pushed-sent
recon = {r["node_id"]: r for r in f.node_reconciliation()}
print("S recon:", recon["S"])
# pushed=6, sent=6, end_inventory=0, unsupplied=4
assert recon["S"]["unsupplied"] == 4, recon["S"]
assert recon["S"]["end_inventory"] == 0, recon["S"]
assert recon["T"]["conserved"] and recon["S"]["conserved"]
assert all(f.checks().values()), f.checks()

# 货源充足但行程限制：截止1只能发一班
f2 = TimeExpandedFlow(["S", "T"], arcs, "S", "T", set(), {}, total_cargo=10, deadline_hours=1)
f2.run_to_deadline()
print("deadline1 value:", f2.value)
assert f2.value == 2
assert all(f2.checks().values())

# 库存等待：A站容量小，货在A等待，库存边承载等待量
arcs3 = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 4, "travel_minutes": 0},
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 1, "travel_minutes": 0},
]
f3 = TimeExpandedFlow(["S", "A", "T"], arcs3, "S", "T", set(), {"A": 4},
                      total_cargo=8, deadline_hours=3)
f3.run_to_deadline()
print("waiting value (每小时过A 1, h0..h3 => 4):", f3.value)
assert f3.value == 4, f3.value
# A库存上限4：h0 4进站，1发出，3等待；检查各层库存<=4
for h in range(4):
    inv = f3._inventory_at("A", h)
    assert 0 <= inv <= 4, (h, inv)
    print("A inventory h%d =" % h, inv)
assert all(f3.checks().values()), f3.checks()
recon3 = {r["node_id"]: r for r in f3.node_reconciliation()}
assert all(r["conserved"] for r in recon3.values()), recon3
print("recon3:", recon3)
print("\nALL WAITING TESTS PASSED")
