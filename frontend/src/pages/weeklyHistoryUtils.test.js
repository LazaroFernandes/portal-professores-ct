import { describe, it, expect } from 'vitest';
import { summarizeWeek, weekEnd, needsAttention, weeklyActions, attentionReasons } from './weeklyHistoryUtils';
import { weekStart } from './professorAnalysisUtils';
const rows = [
 {id:1,client_id:'a',student_name:'Ágata',entered_at:'2026-10-19T08:00:00',professor:'Anderson',status:'registered',record:{outcome:'completed',pain:'no'}},
 {id:2,client_id:'a',student_name:'Ágata',entered_at:'2026-10-20T08:00:00',professor:'Anderson',status:'not_observed',record:{contact:'not_observed'}},
 {id:3,client_id:'a',student_name:'Ágata',entered_at:'2026-10-21T08:00:00',professor:'Camila',status:'pending'},
 {id:4,client_id:'b',student_name:'Bruno',entered_at:'2026-10-19T08:00:00',professor:'',status:'registered',legacy:true,had_pain:1},
];
describe('weekly history from daily records',()=>{
 it('groups a student once without confusing accesses, registration and observation',()=>{const s=summarizeWeek(rows);expect([s.unique_students,s.total,s.registered,s.not_observed,s.pending]).toEqual([2,4,2,1,1]);expect(s.students[0].records.map(r=>r.id)).toEqual([1,2,3]);});
 it('preserves responsible teacher per daily entry and coherent filtered counts',()=>{const s=summarizeWeek(rows,{professor:'Anderson',search:'agata'});expect(s.total).toBe(2);expect(s.teams).toEqual([{name:'Anderson',total:2,registered:1,not_observed:1,pending:0}]);});
 it('keeps all days of students with pending records',()=>{expect(summarizeWeek(rows,{situation:'pending'}).students[0].records.length).toBe(3);expect(summarizeWeek(rows,{professor:'__unassigned'}).total).toBe(1);});
 it('includes legacy daily discomfort in exceptions',()=>{expect(needsAttention(rows[3])).toBe(true);expect(summarizeWeek(rows,{situation:'attention'}).unique_students).toBe(2);});
 it('uses Monday through Sunday even across year boundaries',()=>{expect(weekStart('2027-01-03')).toBe('2026-12-28');expect(weekEnd('2026-12-28')).toBe('2027-01-03');});
 it('reflects corrected daily records without a separate weekly copy',()=>{expect(summarizeWeek(rows.map(r=>r.id===3?{...r,status:'registered'}:r)).pending).toBe(0);expect(summarizeWeek([]).unique_students).toBe(0);});
});

describe('weekly manager follow-ups', () => {
 const range = {start:'2026-10-19',end:'2026-10-25',clientIds:['a']};
 const event = (created_at,actor='Anderson') => ({created_at,actor,payload:{event:'updated',after:{status:'resolved',result:'Retorno realizado'}}});
 const actions = [
  {id:1,client_id:'a',student_name:'Ágata',created_at:'2026-10-10T10:00:00-03:00',assigned_to:'Camila',status:'in_progress',events:[]},
  {id:2,client_id:'b',student_name:'Bruno',created_at:'2026-10-10T10:00:00-03:00',assigned_to:'Camila',status:'resolved',events:[event('2026-10-20T10:00:00-03:00')]},
  {id:3,client_id:'c',student_name:'Carlos',created_at:'2026-10-10T10:00:00-03:00',status:'resolved',events:[event('2026-10-19T01:00:00Z')]},
 ];
 it('includes existing open follow-ups and weekly resolutions without visits', () => {expect(weeklyActions(actions,range).map(a=>a.id)).toEqual([1,2]);});
 it('uses Sao Paulo week boundaries and never includes prior-week updates', () => {expect(weeklyActions([actions[2]],range)).toEqual([]);});
 it('filters by actor as well as current assignee without inventing who acted', () => {const result=weeklyActions(actions,{...range,professor:'Anderson'});expect(result.map(a=>a.id)).toEqual([2]);expect(result[0].weeklyEvents[0].actor).toBe('Anderson');});
 it('explains each attention signal and keeps missing registration distinct',()=>{expect(attentionReasons({status:'pending'})).toEqual([]);expect(attentionReasons({record:{pain:'yes',outcome:'interrupted',follow_up:true}})).toEqual(['Desconforto relatado','Treino interrompido','Retorno solicitado']);});
});
