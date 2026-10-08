"use client";

import { useId, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NewsTaxonomy } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

function TaxonomyForm({ kind, item }: { kind: "topics" | "categories"; item?: NewsTaxonomy }) {
  const id = useId();
  const router = useRouter();
  const mutation = useNewsMutation();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();
    if (!name) { mutation.setError("Укажите название."); return; }
    const result = await mutation.run<NewsTaxonomy>(`/${kind}${item ? `/${item.id}` : ""}`, { name, description: String(data.get("description") ?? "").trim(), active: data.has("active") }, item ? "PATCH" : "POST");
    if (result) { mutation.setMessage(item ? "Изменения сохранены." : "Запись добавлена."); if (!item) form.reset(); router.refresh(); }
  }
  return <form className="news-stack" onSubmit={save} aria-busy={mutation.pending}>
    <div className="admin-field"><label htmlFor={`${id}-name`}>Название (обязательно)</label><input id={`${id}-name`} name="name" required maxLength={120} defaultValue={item?.name ?? ""} disabled={mutation.pending} /></div>
    <div className="admin-field"><label htmlFor={`${id}-description`}>Описание для анализа</label><textarea id={`${id}-description`} name="description" rows={3} maxLength={3000} defaultValue={item?.description ?? ""} disabled={mutation.pending} /></div>
    <label className="news-check"><input type="checkbox" name="active" defaultChecked={item?.active ?? true} disabled={mutation.pending} />Использовать при анализе</label>
    <div><button className="admin-button" type="submit" disabled={mutation.pending}>{item ? "Сохранить изменения" : kind === "topics" ? "Добавить тему" : "Добавить рубрику"}</button></div>
    <NewsFeedback {...mutation} />
  </form>;
}

export function NewsTaxonomyManager({ topics, categories }: { topics: NewsTaxonomy[]; categories: NewsTaxonomy[] }) {
  return <div className="admin-grid-two">{([{ kind: "topics", title: "Темы", items: topics }, { kind: "categories", title: "Рубрики", items: categories }] as const).map(group => <section key={group.kind} className="admin-section news-stack">
    <h2>{group.title}</h2>
    {group.items.length ? <ul className="news-taxonomy-list">{group.items.map(item => <li key={item.id}><details className="news-taxonomy-edit">
      <summary>{item.name} <span className="admin-muted">{item.active ? "Активна" : "Неактивна"}</span></summary><TaxonomyForm kind={group.kind} item={item} />
    </details></li>)}</ul> : <p className="admin-muted">Пока нет записей. Добавьте первую ниже.</p>}
    <h3>{group.kind === "topics" ? "Новая тема" : "Новая рубрика"}</h3><TaxonomyForm kind={group.kind} />
  </section>)}</div>;
}
