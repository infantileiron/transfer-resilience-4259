import sys
sys.path.insert(0, "/workspace/backend")
from src.services.timeflow import TimeExpandedFlow

# A->T 每小时仅1箱且行程1；S->A 零时长可一次进4。截止4。
# h0 进货4到A；出站班次 h0->T@1, h1->T@2, h2->T@3, h3->T@4 共4班，
# 但货若都在h0进A，h0只能发1，其余3箱必须经库存边在A逐小时等待。
# 为阻止“留在S延迟发货”，把 S->A 也设为只在早期高效：这里 S 无库存等待优势——
# 直接把总货量4、S->A容量4，观察最优解是否使用A库存边。
arcs = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 4, "travel_minutes": 0},
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 1, "travel_minutes": 60},
]
f = TimeExpandedFlow(["S", "A", "T"], arcs, "S", "T", set(), {"A": 4},
                     total_cargo=4, deadline_hours=4)
f.run_to_deadline()
print("delivered:", f.value, "(期望4)")
for h in range(5):
    print(" h%d" % h, {n: f._inventory_at(n, h) for n in ["S", "A", "T"]})
storage_flows = [(h, f.residual[i]["flow"]) for (n, h), i in f.storage_index.items()
                 if n == "A" and f.residual[i]["flow"] > 0]
print("A storage edges with flow:", storage_flows)
# 两种最优解都合法：要么货留S延迟发，要么进A等待。断言至少总送达=4且守恒/库存约束成立。
assert f.value == 4
assert all(f.checks().values()), f.checks()
for r in f.node_reconciliation():
    print(r)
print("\nOPTIMAL FLOW VALID (waiting or source-delay both legal)")
