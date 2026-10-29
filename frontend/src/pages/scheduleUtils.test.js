import { describe, expect, it } from 'vitest';
import { monthSummary, overlaps } from './scheduleUtils';
describe('escala mensal', () => {
  it('conta os sábados reais e suas horas sem duplicar o total', () => {
    const shifts = [{day:0,start:'08:00',end:'12:00'},{day:5,start:'08:30',end:'11:00'}];
    expect(monthSummary(shifts,'2026-10')).toEqual({total:1710,saturdays:5,saturdayMinutes:750,perSaturday:150});
    expect(monthSummary(shifts,'2026-02')).toEqual({total:1560,saturdays:4,saturdayMinutes:600,perSaturday:150});
  });
  it('identifica horários parciais e limites sem sobreposição', () => {
    const shift={day:1,start:'08:30',end:'10:00'};
    expect(overlaps(shift,1,480,540)).toBe(true);
    expect(overlaps(shift,1,600,660)).toBe(false);
    expect(overlaps(shift,2,480,540)).toBe(false);
  });
});

import { coverageRange } from './scheduleUtils';
it('counts real and test professors separately and respects changes within the hour', () => {
 const teachers=[{source:'nextfit',shifts:[{day:0,start:'05:00',end:'08:00'}]},{source:'nextfit',shifts:[{day:0,start:'06:30',end:'13:00'}]},{source:'test',shifts:[{day:0,start:'05:00',end:'12:00'}]}];
 expect(coverageRange(teachers,0,300,360)).toEqual({min:1,max:1});
 expect(coverageRange(teachers,0,360,420)).toEqual({min:1,max:2});
 expect(coverageRange(teachers,0,480,540)).toEqual({min:1,max:1});
 expect(coverageRange(teachers,0,300,360,'test')).toEqual({min:1,max:1});
 expect(coverageRange(teachers,1,300,360)).toEqual({min:0,max:0});
});
