import type { NewsSourceSchedule } from "./types";

export const sourceTimezone = "Europe/Samara";
export const sourceWeekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const shortWeekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

export function sourceDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: sourceTimezone, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function sourceToday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: sourceTimezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map(type => parts.find(part => part.type === type)?.value).join("-");
}

export function sourceScheduleSummary(schedule: NewsSourceSchedule): string {
  const times = [...schedule.times].sort().join(", ");
  if (schedule.mode === "weekly") return `По дням недели: ${[...schedule.weekdays].sort((a, b) => a - b).map(day => shortWeekdays[day]).join(", ")} · ${times}`;
  if (schedule.mode === "interval_days") {
    const date = schedule.start_date.split("-").reverse().join(".");
    return `Каждые ${schedule.every_days} дн. с ${date} · ${times}`;
  }
  return `Ежедневно · ${times}`;
}

export function sourceScheduleError(schedule: NewsSourceSchedule): string {
  if (schedule.times.length < 1 || schedule.times.length > 12 || schedule.times.some(time => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) return "Укажите от 1 до 12 времён проверки в формате ЧЧ:ММ.";
  if (new Set(schedule.times).size !== schedule.times.length) return "Времена проверки должны различаться.";
  if (schedule.mode === "weekly" && !schedule.weekdays.length) return "Выберите хотя бы один день недели.";
  if (schedule.mode === "interval_days") {
    if (!Number.isInteger(schedule.every_days) || schedule.every_days < 1 || schedule.every_days > 365) return "Укажите целое число дней от 1 до 365.";
    const parsed = new Date(`${schedule.start_date}T12:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(schedule.start_date) || !Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== schedule.start_date) return "Укажите существующую дату первого дня расписания.";
  }
  return "";
}
