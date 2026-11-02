import {expect,it} from 'vitest';
import {replicationPlan} from './replicateSchedule';
const shifts=[{day:0,start:'05:30',end:'08:00'},{day:0,start:'17:15',end:'20:00'},{day:1,start:'09:00',end:'12:00'},{day:6,start:'10:00',end:'12:00'}];
it('copies all shifts with minutes and breaks, preserving occupied days by default',()=>{
 const result=replicationPlan(shifts,0,[0,1,2,2]);
 expect(result.applied).toEqual([2]);expect(result.skipped).toEqual([1]);
 expect(result.shifts.filter(s=>s.day===2)).toEqual(shifts.slice(0,2).map(s=>({...s,day:2})));
 expect(result.shifts.filter(s=>s.day===1)).toEqual([shifts[2]]);expect(shifts).toHaveLength(4);
});
it('explicit replacement removes destination shifts, preserves source and other days, and is repeatable',()=>{
 const result=replicationPlan(shifts,0,[1,2,3,4,5,6],'replace');
 expect(result.replaced).toEqual([1,6]);expect(result.shifts).toHaveLength(14);
 expect(result.shifts.filter(s=>s.day===0)).toEqual(shifts.slice(0,2));
 expect(replicationPlan(result.shifts,0,[1,2,3,4,5,6],'replace').shifts).toEqual(result.shifts);
});
it('rejects absent source, empty targets, invalid times and overlapping shifts',()=>{
 expect(()=>replicationPlan(shifts,5,[1])).toThrow();expect(()=>replicationPlan(shifts,0,[0])).toThrow();
 expect(()=>replicationPlan([{day:0,start:'',end:'12:00'}],0,[1])).toThrow();
 expect(()=>replicationPlan([{day:0,start:'12:00',end:'08:00'}],0,[1])).toThrow();
 expect(()=>replicationPlan([...shifts,{day:0,start:'07:00',end:'09:00'}],0,[1])).toThrow();
});
