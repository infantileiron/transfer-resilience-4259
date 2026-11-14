import sys
sys.path.insert(0, "/workspace/backend")
from src.services.timeflow import TimeExpandedFlow

# S->A 零时长：货在 h0 即可全部进A，留S并不比进A更优（都能等），
# 但当 A->T 为长行程慢车、截止受限时，部分货进A后注定赶不上，
# 最大流不会推注定失败的货。改用：A->T 零时长容量1（每小时1班），
# S->A 零时长容量3。截止3。货 h0 进3到A，A每小时放1，需在A等待。
arcs = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 3, "travel_minutes": 0},
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 1, "travel_minutes": 0},
]
f = TimeExpandedFlow(["S", "A", "T"], arcs, "S", "T", set(), {"A": 3},
                     total_cargo=3, deadline_hours=2)
f.run_to_deadline()
print("delivered:", f.value, "(h0,h1,h2 各1 => 3)")
for h in range(3):
    print(" h%d" % h, {n: f._inventory_at(n, h) for n in ["S", "A", "T"]})
# 两种最优解等价（留S等 或 进A等），均合法。验证库存上限与守恒严格成立即可。
assert f.value == 3
assert all(f.checks().values()), f.checks()
# 手动制造非最优但可行的等待流：直接断言库存边容量=库存上限且可承载
idx = f.storage_index[("A", 0)]
cap_edge = f.residual[idx]
print("A storage edge capacity:", cap_edge["capacity"] + cap_edge["flow"],
      "flow:", cap_edge["flow"])
assert cap_edge["capacity"] + cap_edge["flow"] == 3  # 总容量守恒
for r in f.node_reconciliation():
    print(r)
print("\nSTORAGE CAPACITY BOUND OK; waiting may legitimately occur at S or A")
