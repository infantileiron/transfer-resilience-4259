<script setup lang="ts">import {ref,computed} from 'vue';import type {ShipmentRow} from '../../types/domain';
const props=defineProps<{rows:ShipmentRow[];deadline:number}>();
const hour=ref(0);
const hours=computed(()=>Array.from(new Set(props.rows.map(r=>r.hour))).sort((a,b)=>a-b));
const shown=computed(()=>props.rows.filter(r=>r.hour===hour.value&&r.shipped>0));
</script><template><div class="hour-filter"><label>发车小时<select :value="hour" @change="hour=Number(($event.target as HTMLSelectElement).value)"><option v-for="h in hours" :key="h" :value="h">第 {{h}} 小时</option></select></label><span class="caption">仅显示当小时实际发箱的班次；容量沿用该边每小时箱量。</span></div><div class="table-scroll"><table><thead><tr><th>发车小时</th><th>边ID / 方向</th><th>行程小时</th><th>到达小时</th><th>容量</th><th>发箱量</th></tr></thead><tbody><tr v-for="r in shown" :key="r.arc_id+'-'+r.hour"><td>{{r.hour}}</td><td><b>{{r.arc_id}}</b><small>{{r.source}} → {{r.target}}</small></td><td>{{r.lead_hours}}</td><td>{{r.arrive_hour}}</td><td>{{r.capacity}}</td><td>{{r.shipped}}</td></tr><tr v-if="!shown.length"><td colspan="6">该小时无发箱班次</td></tr></tbody></table></div></template>
