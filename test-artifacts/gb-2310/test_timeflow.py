# 限时发运时间展开最大流 · 独立验证（标准库，python -I 运行）
# 运行：PYTHONPATH=/workspace/backend python3 -I /workspace/test-artifacts/gb-2310/test_timeflow.py
import sys
sys.path.insert(0, "/workspace/backend")
from src.services.timeflow import TimeExpandedFlow, ceil_hours

passed = []
failed = []


def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  -> {detail}"))


def caps(**kw):
    return kw


# ---------- 1. 行程向上取整 ----------
print("[1] ceil_hours")
check("0分钟->0(当场转运)", ceil_hours(0) == 0)
check("1分钟->1小时", ceil_hours(1) == 1)
check("60分钟->1小时", ceil_hours(60) == 1)
check("61分钟->2小时", ceil_hours(61) == 2)
check("120分钟->2小时", ceil_hours(120) == 2)

# ---------- 2. 最小网络：S->A->T，容量5，行程1小时，截止2 ----------
print("[2] 链式网络 截止2小时")
arcs2 = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 5, "travel_minutes": 60},
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 5, "travel_minutes": 60},
]
nodes2 = ["S", "A", "T"]
f = TimeExpandedFlow(nodes2, arcs2, "S", "T", set(), caps(A=100), total_cargo=50, deadline_hours=2)
f.run_to_deadline()
# h0: S->A 5 (到A@1); h1: A->T 5 (到T@2); 截止2送达=5。h2发车到T@3超时不可用
check("截止2最多送达5", f.value == 5, f"got {f.value}")
check("全部检查通过", all(f.checks().values()), f.checks())
recon = {r["node_id"]: r for r in f.node_reconciliation()}
check("S守恒", recon["S"]["conserved"], recon["S"])
check("A守恒", recon["A"]["conserved"], recon["A"])
check("T守恒", recon["T"]["conserved"], recon["T"])
check("S未投放45", recon["S"]["unsupplied"] == 45, recon["S"])
check("S站内库存0(已全部发走)", recon["S"]["end_inventory"] == 0, recon["S"])
check("T送达5", recon["T"]["delivered"] == 5, recon["T"])

# ---------- 3. 截止3：可发两班 ----------
print("[3] 链式网络 截止3小时")
f3 = TimeExpandedFlow(nodes2, arcs2, "S", "T", set(), caps(A=100), 50, 3)
f3.run_to_deadline()
# h0 S->A@1, h1 A->T@2(5); h1 S->A@2, h2 A->T@3(5) => 10
check("截止3最多送达10", f3.value == 10, f"got {f3.value}")
check("全部检查通过", all(f3.checks().values()), f3.checks())

# ---------- 4. 库存上限约束：A库存上限3（节点拆分后当场转运同样受限）----------
print("[4] 库存上限 A=3")
f4 = TimeExpandedFlow(nodes2, arcs2, "S", "T", set(), caps(A=3), 50, 3)
f4.run_to_deadline()
# 每小时最多3箱经过A；h1到T 3, h2到T 3 => 6
check("库存受限送达6", f4.value == 6, f"got {f4.value}")
check("A各层库存不超过3", all(
    f4._inventory_at("A", h) <= 3 for h in range(4)))
check("全部检查通过", all(f4.checks().values()), f4.checks())
inv4 = {(r["hour"], r["node_id"]): r["inventory"] for r in f4.inventory_table()}
recon4 = {r["node_id"]: r for r in f4.node_reconciliation()}
check("S未投放=50-6=44", recon4["S"]["unsupplied"] == 44, recon4["S"])

# ---------- 5. 零时长边当场转运 ----------
print("[5] 零时长边")
arcs5 = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 4, "travel_minutes": 0},
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 4, "travel_minutes": 0},
]
f5 = TimeExpandedFlow(nodes2, arcs5, "S", "T", set(), caps(A=100), 50, 1)
f5.run_to_deadline()
# h0 当场 S->A->T 4箱；h1再4箱 => 8
check("零时长当场转运 截止1送达8", f5.value == 8, f"got {f5.value}")
check("全部检查通过", all(f5.checks().values()), f5.checks())

# ---------- 6. 平行边独立容量 ----------
print("[6] 平行边")
arcs6 = [
    {"arc_id": "e1", "source": "S", "target": "T", "capacity": 3, "travel_minutes": 60},
    {"arc_id": "e2", "source": "S", "target": "T", "capacity": 2, "travel_minutes": 60},
]
f6 = TimeExpandedFlow(["S", "T"], arcs6, "S", "T", set(), caps(), 50, 1)
f6.run_to_deadline()
# 两条平行边各走各的，h0发出5到T@1 => 5
check("平行边容量相加=5", f6.value == 5, f"got {f6.value}")
ships = {(r["arc_id"], r["hour"]): r["shipped"] for r in f6.shipments_table()}
check("e1走3", ships[("e1", 0)] == 3)
check("e2走2", ships[("e2", 0)] == 2)

# ---------- 7. 停用边与零容量边不参与 ----------
print("[7] 停用/零容量边排除")
arcs7 = [
    {"arc_id": "e1", "source": "S", "target": "T", "capacity": 9, "travel_minutes": 60},
    {"arc_id": "e2", "source": "S", "target": "T", "capacity": 0, "travel_minutes": 60},
]
f7 = TimeExpandedFlow(["S", "T"], arcs7, "S", "T", {"e1"}, caps(), 50, 1)
f7.run_to_deadline()
check("停用唯一通路送达0", f7.value == 0, f"got {f7.value}")
check("零容量边无发运记录", all(r["arc_id"] != "e2" for r in f7.shipments_table()))

# ---------- 8. 货量不足时不会超投 ----------
print("[8] 整箱货量约束")
arcs8 = [{"arc_id": "e1", "source": "S", "target": "T", "capacity": 100, "travel_minutes": 0}]
f8 = TimeExpandedFlow(["S", "T"], arcs8, "S", "T", set(), caps(), 7, 2)
f8.run_to_deadline()
check("仅7箱可送达", f8.value == 7, f"got {f8.value}")

# ---------- 9. 检查点：逐小时中断恢复结果一致 ----------
print("[9] 检查点恢复")
arcs9 = [
    {"arc_id": "e1", "source": "S", "target": "A", "capacity": 5, "travel_minutes": 90},   # 2h
    {"arc_id": "e2", "source": "A", "target": "T", "capacity": 5, "travel_minutes": 30},   # 1h
    {"arc_id": "e3", "source": "S", "target": "T", "capacity": 2, "travel_minutes": 60},   # 1h
]
nodes9 = ["S", "A", "T"]
kw = dict(node_ids=nodes9, arcs=arcs9, source="S", sink="T", disabled=set(),
          stock_caps=caps(A=10), total_cargo=40, deadline_hours=5)
full = TimeExpandedFlow(**kw)
full.run_to_deadline()
# 模拟在每个小时中断：从检查点重建后继续，结果必须与一次跑完完全相同
for break_hour in range(0, 5):
    part = TimeExpandedFlow(**kw)
    snapshot = {}
    part.run_to_deadline(on_checkpoint=lambda h, engine: snapshot.update(engine.to_checkpoint()) if h == break_hour else None)
    restored = TimeExpandedFlow.from_checkpoint(snapshot, **kw)
    restored.run_to_deadline()
    same = (restored.value == full.value and
            restored.shipments_table() == full.shipments_table() and
            restored.inventory_table() == full.inventory_table())
    check(f"第{break_hour}小时中断恢复一致", same,
          f"{restored.value} vs {full.value}")
check("全程检查通过", all(full.checks().values()), full.checks())
recon9 = {r["node_id"]: r for r in full.node_reconciliation()}
check("9-A守恒", recon9["A"]["conserved"], recon9["A"])
check("9-T守恒", recon9["T"]["conserved"], recon9["T"])

# ---------- 10. 缺库存上限被拒绝 ----------
print("[10] 输入防护")
try:
    TimeExpandedFlow(nodes2, arcs2, "S", "T", set(), dict(), 50, 2)
    check("缺中转站库存上限报错", False)
except ValueError:
    check("缺中转站库存上限报错", True)
try:
    TimeExpandedFlow(nodes2, arcs2, "S", "T", set(), caps(A=-1), 50, 2)
    check("负库存上限报错", False)
except ValueError:
    check("负库存上限报错", True)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
