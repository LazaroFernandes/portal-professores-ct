import {expect,it} from 'vitest';
import {scenarios,summarizeScenarios} from './flowScenarios';
const cell={need4:2,need3:3,scheduled:2,scheduled_max:3,real_min:1,real_max:2,missing4:0,missing4_min:0,missing3:1,missing3_min:0};
it('compares real-only coverage with combined coverage for both ratios',()=>{
 expect(scenarios(cell,4)).toEqual({need:2,current:{min:1,max:2,missingMin:0,missingMax:1},proposed:{min:2,max:3,missingMin:0,missingMax:0},improvement:1});
 expect(scenarios(cell,3).current.missingMax).toBe(2);
 expect(scenarios(cell,3).proposed.missingMax).toBe(1);
});
it('does not turn missing analysis data into covered hours',()=>{
 const missing={...cell,need4:null};
 expect(scenarios(missing,4).current.missingMax).toBeNull();
 expect(summarizeScenarios([cell,missing],4)).toEqual({count:1,current:1,proposed:0,improved:1,resolved:1});
});
