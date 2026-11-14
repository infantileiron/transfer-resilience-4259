# 限时发运 · 时间展开网络（Time-Expanded Network）最大流
#
# 在已完成推演锁定的同一份边快照上，把“每小时箱量容量 + 行程小时 + 站内库存上限”
# 展开成按小时分层的有向网络，用 Edmonds–Karp 求截止小时内最多送达汇站的整箱货量。
#
# 节点拆分：每个中转站拆成 in/out 两个时点，所有到达货物先入 in，
# 经一条容量=库存上限的站内边(in->out)才能发出或等待，从而库存上限对
# “当场转运”和“等待”同样生效；源/汇站内边容量无穷。
#
# 分层约定（整点发车，行程向上取整到小时，零时长边当场转运）：
#   站内边  (n,in,h) -> (n,out,h)    容量=该站库存上限（源/汇无穷）
#   库存边  (n,out,h) -> (n,in,h+1)  容量=库存上限；货物在站内等待一小时
#   发车边  (u,out,h) -> (v,in,h+lead) 容量=该弧每小时箱量；lead=0 落在同一层
#   货源边  super_source -> (S,in,0) 容量=整箱货量，仅第 0 小时投放
#   送达边  (T,out,h) -> super_sink  容量=无穷，任意层到达即计入送达
#
# 残量网络按小时增量构建：每扩好一层就增广一次，并把完整状态序列化为检查点。
# 计算中断后从最后一个已提交检查点反序列化，继续后续小时；最终最大流值与
# 一次跑完完全一致（同一最终网络的最大流值唯一，残量支持改道）。
import copy
import math
from collections import deque

INF = 10 ** 12  # 源/汇无库存上限时的有限大容量，避免使用不可序列化的 math.inf


def ceil_hours(travel_minutes):
 # 行程向上取整到小时；零时长边返回 0，可当场转运
 if travel_minutes <= 0:
  return 0
 return max(1, math.ceil(travel_minutes / 60.0))


class TimeExpandedFlow:
 def __init__(self, node_ids, arcs, source, sink, disabled, stock_caps,
              total_cargo, deadline_hours):
  self.node_ids = list(node_ids)
  self.source = source
  self.sink = sink
  self.blocked = set(disabled)
  self.total_cargo = total_cargo
  self.deadline = deadline_hours
  # 仅启用且正容量的边参与发运；按边ID排序保证确定性（平行/反向边各自独立）
  self.arcs = sorted(
   [dict(a, lead=ceil_hours(a["travel_minutes"])) for a in arcs
    if a["arc_id"] not in self.blocked and a["capacity"] > 0],
   key=lambda a: a["arc_id"])
  # 库存上限：源站与汇站不限，中转站取传入上限，缺省拒绝而非静默放宽
  self.stock_caps = {}
  for n in self.node_ids:
   if n in (source, sink):
    self.stock_caps[n] = INF
   elif n not in stock_caps:
    raise ValueError(f"中转站 {n} 缺少库存上限")
   else:
    cap = stock_caps[n]
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
     raise ValueError(f"中转站 {n} 库存上限须为非负整数")
    self.stock_caps[n] = cap
  self.super_source = "@@src"
  self.super_sink = "@@sink"
  # 残量边表：每条边占正/反两个索引，reverse 互指（与 maxflow.py 同构）
  self.residual = []
  self.adjacency = {}
  # 记录原始发车边的正向残量索引，供逐小时发运台账反查
  self.ship_index = {}  # (arc_id, hour) -> forward residual index
  # 记录站内边/库存边正向索引，供库存台账反查
  self.station_index = {}  # (node, hour) -> in->out 正向索引
  self.storage_index = {}  # (node, hour) -> out,h -> in,h+1 正向索引
  self.value = 0
  self.built_hours = -1  # 已构建到的小时层（-1 表示尚未开始）

 def _in(self, node, hour):
  return f"{node}#in@{hour}"

 def _out(self, node, hour):
  return f"{node}#out@{hour}"

 def _ensure_vertex(self, vertex):
  if vertex not in self.adjacency:
   self.adjacency[vertex] = []

 def _add_edge(self, u, v, capacity, kind, ref=None):
  # 新增一条独立正/反残量对；平行边、反向边、零时长边都不合并
  self._ensure_vertex(u)
  self._ensure_vertex(v)
  forward = len(self.residual)
  reverse = forward + 1
  self.residual.append({"u": u, "v": v, "capacity": capacity, "reverse": reverse,
                        "kind": kind, "ref": ref, "flow": 0})
  self.residual.append({"u": v, "v": u, "capacity": 0, "reverse": forward,
                        "kind": kind, "ref": ref, "flow": 0})
  self.adjacency[u].append(forward)
  self.adjacency[v].append(reverse)
  return forward

 def _augment(self):
  # 在当前残量网络上反复 BFS 增广，直到超级汇不可达；增量计入 self.value
  while True:
   parent = {self.super_source: None}
   queue = deque([self.super_source])
   while queue and self.super_sink not in parent:
    u = queue.popleft()
    for index in self.adjacency[u]:
     edge = self.residual[index]
     if edge["capacity"] > 0 and edge["v"] not in parent:
      parent[edge["v"]] = index
      queue.append(edge["v"])
      if edge["v"] == self.super_sink:
       break
   if self.super_sink not in parent:
    break
   path = []
   node = self.super_sink
   while node != self.super_source:
    index = parent[node]
    path.append(index)
    node = self.residual[index]["u"]
   delta = min(self.residual[i]["capacity"] for i in path)
   for index in path:
    edge = self.residual[index]
    edge["capacity"] -= delta
    self.residual[edge["reverse"]]["capacity"] += delta
    edge["flow"] += delta
    self.residual[edge["reverse"]]["flow"] -= delta
   self.value += delta

 def build_hour(self, hour):
  # 增量构建第 hour 层（hour 从 0 到 deadline），随后立即增广
  if hour != self.built_hours + 1:
   raise ValueError("小时层必须按顺序构建")
  h = hour
  for n in self.node_ids:
   self._ensure_vertex(self._in(n, h))
   self._ensure_vertex(self._out(n, h))
  # 站内边 in->out：容量即库存上限，强制所有到站货物（含当场转运）受约束
  for n in self.node_ids:
   idx = self._add_edge(self._in(n, h), self._out(n, h),
                        self.stock_caps[n], "station", n)
   self.station_index[(n, h)] = idx
  # 第 0 层投放整箱货量：超级源 -> 源站 in@0
  if h == 0:
   self._add_edge(self.super_source, self._in(self.source, 0),
                  self.total_cargo, "supply", None)
  # 库存边：out,h -> in,h+1，货物等待一小时（最后一层之后无处可等）
  if h < self.deadline:
   for n in self.node_ids:
    idx = self._add_edge(self._out(n, h), self._in(n, h + 1),
                         self.stock_caps[n], "storage", n)
    self.storage_index[(n, h)] = idx
  # 发车边：整点发车，lead=0 时 out,h -> in,h 实现当场转运
  for arc in self.arcs:
   arrive = h + arc["lead"]
   if arrive > self.deadline:
    continue  # 截止后到达的班次不进入网络，货物不能超时到达
   idx = self._add_edge(self._out(arc["source"], h),
                        self._in(arc["target"], arrive),
                        arc["capacity"], "ship", arc["arc_id"])
   self.ship_index[(arc["arc_id"], h)] = idx
  # 送达边：本层汇站 out -> 超级汇
  self._add_edge(self._out(self.sink, h), self.super_sink, INF, "deliver", None)
  self._augment()
  self.built_hours = h

 def run_to_deadline(self, on_checkpoint=None):
  for h in range(self.built_hours + 1, self.deadline + 1):
   self.build_hour(h)
   if on_checkpoint:
    on_checkpoint(h, self)
  return self.value

 # ---- 检查点序列化 / 反序列化（仅用于中断恢复，不向前端暴露半成品）----
 def to_checkpoint(self):
  # 深拷贝：调用方可能在保存检查点后继续构建后续小时，浅引用会被原地增广污染
  return copy.deepcopy({"residual": self.residual, "adjacency": self.adjacency,
          "ship_index": {f"{k[0]}|{k[1]}": v for k, v in self.ship_index.items()},
          "station_index": {f"{k[0]}|{k[1]}": v for k, v in self.station_index.items()},
          "storage_index": {f"{k[0]}|{k[1]}": v for k, v in self.storage_index.items()},
          "value": self.value, "built_hours": self.built_hours})

 @staticmethod
 def _unpair(map_state):
  out = {}
  for key, index in map_state.items():
   name, hour = key.split("|", 1)
   out[(name, int(hour))] = index
  return out

 @classmethod
 def from_checkpoint(cls, state, node_ids, arcs, source, sink, disabled,
                     stock_caps, total_cargo, deadline_hours):
  obj = cls(node_ids, arcs, source, sink, disabled, stock_caps,
            total_cargo, deadline_hours)
  obj.residual = state["residual"]
  obj.adjacency = state["adjacency"]
  obj.ship_index = cls._unpair(state["ship_index"])
  obj.station_index = cls._unpair(state["station_index"])
  obj.storage_index = cls._unpair(state["storage_index"])
  obj.value = state["value"]
  obj.built_hours = state["built_hours"]
  return obj

 # ---- 结果提取：逐小时逐边发运、站内库存、节点对账 ----
 def shipments_table(self):
  out = []
  for arc in self.arcs:
   for h in range(self.deadline + 1):
    idx = self.ship_index.get((arc["arc_id"], h))
    if idx is None:
     continue
    out.append({"hour": h, "arc_id": arc["arc_id"], "source": arc["source"],
                "target": arc["target"], "lead_hours": arc["lead"],
                "capacity": arc["capacity"], "shipped": self.residual[idx]["flow"],
                "arrive_hour": h + arc["lead"]})
  out.sort(key=lambda r: (r["hour"], r["arc_id"]))
  return out

 def _station_throughput(self, node, hour):
  # 第 hour 层进入该站的货量（站内边 in->out 的累计流量）
  return self.residual[self.station_index[(node, hour)]]["flow"]

 def _sent_at_hour(self, node, hour):
  # 第 hour 层该站实际发出的货量（仅统计本层确实创建的发车边，
  # 截止后来不及到达而未建边的班次不计）
  total = 0
  for arc in self.arcs:
   idx = self.ship_index.get((arc["arc_id"], hour))
   if idx is not None and arc["source"] == node:
    total += self.residual[idx]["flow"]
  return total

 def _inventory_at(self, node, hour):
  # 第 hour 小时末仍在站内的库存：
  # 非末层 = 等待到下一小时的库存边流量；
  # 末层无库存边，= 当层进站量 − 当层实际发出 − （汇站）当层送达。
  idx = self.storage_index.get((node, hour))
  if idx is not None:
   return self.residual[idx]["flow"]
  held = self._station_throughput(node, hour)
  return held - self._sent_at_hour(node, hour) - (
   self.delivered_at_hour(hour) if node == self.sink else 0)

 def delivered_at_hour(self, hour):
  # 第 hour 层经送达边进入超级汇的货量
  total = 0
  for i in self.adjacency.get(self._out(self.sink, hour), []):
   edge = self.residual[i]
   if edge["kind"] == "deliver" and edge["v"] == self.super_sink:
    total += edge["flow"]
  return total

 def _supply_pushed(self):
  # 已从超级源投放到源站的货量（货源边累计流量）；受网络瓶颈限制可能小于总货量
  for i in self.adjacency.get(self.super_source, []):
   edge = self.residual[i]
   if edge["kind"] == "supply":
    return edge["flow"]
  return 0

 def inventory_table(self):
  # hour 表示第 hour 小时末的站内库存（源站为已投放但未发出，汇站为到而未送达）；
  # 源站因瓶颈尚未投放的货不在任何站点内，单独在 node_reconciliation 的
  # unsupplied 字段对账，避免把超级源上的未用货量误记为站内库存。
  out = []
  for h in range(self.deadline + 1):
   for n in self.node_ids:
    out.append({"hour": h, "node_id": n, "inventory": self._inventory_at(n, h)})
  out.sort(key=lambda r: (r["hour"], r["node_id"]))
  return out

 def node_reconciliation(self):
  # 按节点对账整箱货：投放/收到、发出、期末库存；源站单列未投放，汇站列送达
  ships = self.shipments_table()
  pushed = self._supply_pushed()
  rows = []
  for n in self.node_ids:
   received = sum(r["shipped"] for r in ships if r["target"] == n)
   sent = sum(r["shipped"] for r in ships if r["source"] == n)
   end_stock = self._inventory_at(n, self.deadline)
   if n == self.source:
    unsupplied = self.total_cargo - pushed
    # 总货量 = 未投放 + 已投放；已投放 = 发出 + 期末站内库存
    balance = self.total_cargo - unsupplied - sent - end_stock
    role = "source"
   elif n == self.sink:
    unsupplied = 0
    # 收到 = 已送达超级汇 + 期末仍在汇站
    balance = received - self.value - end_stock
    role = "sink"
   else:
    unsupplied = 0
    # 收到 = 发出 + 期末库存
    balance = received - sent - end_stock
    role = "transfer"
   rows.append({"node_id": n, "role": role,
                "supplied": pushed if n == self.source else 0,
                "unsupplied": unsupplied, "received": received, "sent": sent,
                "delivered": self.value if n == self.sink else 0,
                "end_inventory": end_stock, "balance": balance,
                "conserved": balance == 0})
  return rows

 def checks(self):
  ships = self.shipments_table()
  recon = self.node_reconciliation()
  bounds = all(0 <= r["shipped"] <= r["capacity"] for r in ships)
  no_early = all(r["arrive_hour"] <= self.deadline for r in ships)
  stock_ok = all(0 <= r["inventory"] <= self.stock_caps[r["node_id"]]
                 for r in self.inventory_table())
  conserved = all(r["conserved"] for r in recon)
  delivered_ok = self.value <= self.total_cargo
  return {"shipment_capacity_bounds": bounds,
          "no_arrival_after_deadline": no_early,
          "inventory_within_limits": stock_ok,
          "node_conservation": conserved,
          "delivered_within_cargo": delivered_ok}
