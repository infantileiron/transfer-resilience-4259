export const ROLES:Record<string,string>={admin:'管理员',analyst:'联运分析员',viewer:'只读复核员'};
export const RUN_STATUS:Record<string,string>={queued:'排队中',running:'推演中',completed:'已完成',failed:'失败'};
export const PHASES:Record<string,string>={baseline:'基线网络',outage:'停用方案'};
export const DECISIONS:Record<string,string>={accepted:'接受并记录边界',needs_attention:'需要继续核查'};
export const CHECKS:Record<string,string>={flow_capacity_bounds:'逐边容量界',conservation:'逐节点流守恒',maxflow_equals_mincut:'最大流等于最小割',sink_not_residual_reachable:'残量源侧不含汇'};
export const SHIPMENT_CHECKS:Record<string,string>={shipment_capacity_bounds:'逐班发车容量界',no_arrival_after_deadline:'无超时到达',inventory_within_limits:'站内库存不超上限',node_conservation:'逐节点收发库存守恒',delivered_within_cargo:'送达不超整箱货量'};
export const MAX_SHIPMENT_HOURS=72;
