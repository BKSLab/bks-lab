"use client";

import { Pencil } from "lucide-react";
import { useRef, useState } from "react";
import { sourceScheduleSummary } from "@/lib/news-api/schedule";
import type { NewsSource } from "@/lib/news-api/types";
import { NewsSourceScheduleDialog } from "./NewsSourceScheduleDialog";

export function NewsSourceSchedule({ source, onSaved }: { source: NewsSource; onSaved: (source: NewsSource) => void }) {
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const summary = sourceScheduleSummary(source.schedule);

  return <div className="news-source-schedule">
    <button
      ref={trigger}
      type="button"
      className="news-source-schedule-trigger"
      aria-label={`Изменить расписание: ${source.name}. ${summary}`}
      aria-haspopup="dialog"
      onClick={() => { setMessage(""); setOpen(true); }}
    >
      <span>{summary}</span>
      <Pencil size={16} aria-hidden="true" />
    </button>
    {open && <NewsSourceScheduleDialog
      source={source}
      restoreFocus={trigger}
      onClose={() => setOpen(false)}
      onSaved={updated => {
        onSaved(updated);
        setMessage("Расписание сохранено.");
        setOpen(false);
      }}
    />}
    <p className="admin-muted news-feedback" role="status">{message}</p>
  </div>;
}
