<script setup lang="ts">import type {ReconRow} from '../../types/domain';
defineProps<{rows:ReconRow[]}>();
const roleName:Record<string,string>={source:'源站',sink:'汇站',transfer:'中转站'};
</script><template><div class="table-scroll"><table><thead><tr><th>节点</th><th>角色</th><th>投放</th><th>未投放</th><th>收到</th><th>发出</th><th>累计送达</th><th>期末库存</th><th>余额</th><th>守恒</th></tr></thead><tbody><tr v-for="r in rows" :key="r.node_id"><td><b>{{r.node_id}}</b></td><td>{{roleName[r.role]||r.role}}</td><td>{{r.supplied}}</td><td>{{r.unsupplied}}</td><td>{{r.received}}</td><td>{{r.sent}}</td><td>{{r.delivered}}</td><td>{{r.end_inventory}}</td><td>{{r.balance}}</td><td><span :class="['tag',{pass:r.conserved}]">{{r.conserved?'通过':'失败'}}</span></td></tr></tbody></table></div></template>
