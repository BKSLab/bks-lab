"use client";

import Link from "next/link";

export default function AdminError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div className="admin-state">
    <h1>Не удалось загрузить панель</h1>
    <p role="alert">Сервис временно недоступен. Попробуйте загрузить страницу ещё раз.</p>
    <button type="button" className="admin-button" onClick={reset}>Повторить</button>
    <Link href="/admin/login" className="admin-link">Перейти ко входу</Link>
  </div>;
}
