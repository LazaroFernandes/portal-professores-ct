export function weekStart(value) {
  const day = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(day.getTime())) return "";
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

export function currentWeek() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return weekStart(`${values.year}-${values.month}-${values.day}`);
}

export function shiftWeek(start, offset) {
  const day = new Date(`${start}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + offset * 7);
  return day.toISOString().slice(0, 10);
}

export function normalized(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
}

export function filterStudents(students, { professor, status, search }) {
  const term = normalized(search).trim();
  return students.filter((student) => (
    (professor === "all" || student.professor === professor)
    && (status === "all" || (status === "pending" ? student.status !== "complete" : student.status === status))
    && (!term || normalized(`${student.name} ${student.professor} ${student.modality}`).includes(term))
  ));
}
