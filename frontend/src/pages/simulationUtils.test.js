import {it,expect} from 'vitest';
import {simulationTeam,simulationError} from './simulationUtils';
import {coverageRange} from './scheduleUtils';
const shift=(start,end)=>({day:0,start,end});
it('inherits official shifts, supports explicit removal and never mutates original',()=>{
 const original=[{id:'real',source:'nextfit',shifts:[shift('05:00','08:00')]},{id:'test',source:'test',shifts:[shift('06:00','07:00')]}];
 const next=simulationTeam(original,{real:[]});
 expect(next[0].shifts).toEqual([]);expect(next[1].shifts).toEqual(original[1].shifts);
 expect(original[0].shifts).toHaveLength(1);
 expect(simulationTeam(original,{})).toEqual(original);
 expect(simulationTeam(original,{removed:[]})).toEqual(original);
});
it('compares minute-accurate handover between adjusted teacher and test',()=>{
 const original=[{id:'real',source:'nextfit',shifts:[shift('08:00','12:00')]},{id:'test',source:'test',shifts:[shift('05:30','06:00')]}];
 const next=simulationTeam(original,{real:[shift('05:00','05:30')]});
 expect(coverageRange(original,0,300,360,'nextfit')).toEqual({min:0,max:0});
 expect(coverageRange(next,0,300,360,null)).toEqual({min:1,max:1});
});
it('rejects partial, inverted or overlapping edits but allows no turns and touching boundaries',()=>{
 expect(simulationError({real:[]})).toBe('');
 expect(simulationError({real:[shift('05:00','05:30'),shift('05:30','06:00')]})).toBe('');
 expect(simulationError({real:[shift('','06:00')]})).not.toBe('');
 expect(simulationError({real:[shift('08:00','07:00')]})).not.toBe('');
 expect(simulationError({real:[shift('05:00','06:00'),shift('05:30','06:30')]})).not.toBe('');
});
