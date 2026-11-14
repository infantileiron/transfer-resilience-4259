<script setup lang="ts">import {computed} from 'vue';import type {DeliveryPoint} from '../../types/domain';
const props=defineProps<{series:DeliveryPoint[];total:number}>();
const W=640,H=220,P=38;
const maxH=computed(()=>Math.max(1,...props.series.map(p=>p.cumulative_delivered)));
const maxX=computed(()=>Math.max(1,props.series.length-1));
function x(i:number){return P+(W-2*P)*i/maxX.value;}
function y(v:number){return H-P-(H-2*P)*v/maxH.value;}
const line=computed(()=>props.series.map((p,i)=>(i===0?'M':'L')+x(i).toFixed(1)+' '+y(p.cumulative_delivered).toFixed(1)).join(' '));
const area=computed(()=>line.value+` L ${x(maxX.value)} ${H-P} L ${x(0)} ${H-P} Z`);
const ticks=computed(()=>{const n=Math.min(5,maxX.value);return Array.from({length:n+1},(_,k)=>Math.round(maxX.value*k/n));});
</script><template><svg class="delivery-curve" :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="逐小时累计送达曲线"><path :d="area" class="curve-area"/><path :d="line" class="curve-line"/><g v-for="(p,i) in series" :key="i"><circle :cx="x(i)" :cy="y(p.cumulative_delivered)" r="2.6" class="curve-dot"><title>第{{i}}小时累计 {{p.cumulative_delivered}} / {{total}}</title></circle></g><line :x1="P" :y1="H-P" :x2="W-P" :y2="H-P" class="axis"/><line :x1="P" :y1="P" :x2="P" :y2="H-P" class="axis"/><g v-for="t in ticks" :key="'x'+t"><text :x="x(t)" :y="H-P+16" class="axis-label" text-anchor="middle">{{t}}</text></g><text :x="W-P" :y="P-12" class="axis-label" text-anchor="end">累计 {{series[series.length-1]?.cumulative_delivered??0}} 箱</text></svg></template>
