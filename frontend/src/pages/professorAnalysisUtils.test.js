import { describe, expect, it } from "vitest";
import { filterStudents, shiftWeek, weekStart } from "./professorAnalysisUtils";

describe("períodos semanais", () => {
  it("usa segunda a domingo e preserva a virada do ano", () => {
    expect(weekStart("2027-01-01")).toBe("2026-12-28");
    expect(weekStart("2026-10-18")).toBe("2026-10-12");
    expect(shiftWeek("2026-12-28", 1)).toBe("2027-01-04");
    expect(shiftWeek("2027-01-04", -1)).toBe("2026-12-28");
    expect(weekStart("")).toBe("");
  });
});

describe("lista de controle", () => {
  const students = [
    { name: "João", professor: "José", modality: "Musculação", status: "partial" },
    { name: "Ana", professor: "José", status: "complete" },
    { name: "Bia", professor: "", status: "empty" },
  ];
  it("combina professor, pendências e pesquisa sem acentos", () => {
    expect(filterStudents(students, { professor: "José", status: "pending", search: "joao" })).toEqual([students[0]]);
    expect(filterStudents(students, { professor: "all", status: "all", search: "musculacao" })).toEqual([students[0]]);
  });
  it("separa sem professor, completos, parciais e em branco", () => {
    expect(filterStudents(students, { professor: "", status: "all" })).toEqual([students[2]]);
    expect(filterStudents(students, { professor: "all", status: "complete" })).toEqual([students[1]]);
    expect(filterStudents(students, { professor: "all", status: "pending" })).toHaveLength(2);
    expect(filterStudents(students, { professor: "all", status: "partial" })).toEqual([students[0]]);
    expect(filterStudents(students, { professor: "all", status: "empty" })).toEqual([students[2]]);
  });
});
