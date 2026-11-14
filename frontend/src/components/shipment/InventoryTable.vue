<script setup lang="ts">import {ref,computed} from 'vue';import type {InventoryRow} from '../../types/domain';
const props=defineProps<{rows:InventoryRow[];limits:Record<string,number>;source:string;sink:string}>();
const hour=ref(0);
const hours=computed(()=>Array.from(new Set(props.rows.map(r=>r.hour))).sort((a,b)=>a-b));
const shown=computed(()=>props.rows.filter(r=>r.hour===hour.value));
function cap(node:string){return node===props.source||node===props.sink?'不限':(props.limits[node]??'—');}
</script><template><div class="hour-filter"><label>库存时点（小时末）<select :value="hour" @change="hour=Number(($event.target as HTMLSelectElement).value)"><option v-for="h in hours" :key="h" :value="h">第 {{h}} 小时末</option></select></label></div><div class="table-scroll"><table><thead><tr><th>节点</th><th>站内库存 / 箱</th><th>库存上限</th><th>状态</th></tr></thead><tbody><tr v-for="r in shown" :key="r.node_id"><td><b>{{r.node_id}}</b></td><td>{{r.inventory}}</td><td>{{cap(r.node_id)}}</td><td><span :class="['tag',{pass:r.node_id===source||r.node_id===sink||r.inventory<=(limits[r.node_id]??0)}]">{{r.inventory>0?'在库':'空'}}</span></td></tr></tbody></table></div></template>
