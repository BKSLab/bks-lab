"use client";

import Link from "next/link";
import { useState } from "react";
import { sourceGroups, type SourceCatalogueEntry, type SourceCatalogueMode } from "@/lib/news-api/catalogue";
import type { NewsSource } from "@/lib/news-api/types";

const modeLabels: Record<SourceCatalogueMode, string> = {
  rss: "RSS / Atom", auto: "Страницы публикаций", read: "Для чтения", api: "API / поиск",
};

function comparableUrl(value: string): string {
  try {
    const url = new URL(value);
    return `${url.origin}${url.pathname.replace(/\/+$/, "")}${url.search}`;
  } catch { return value; }
}

export function NewsSourceCatalogue({ sources, catalogue: sourceCatalogue }: { sources: NewsSource[]; catalogue: SourceCatalogueEntry[] }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [priority, setPriority] = useState("");
  const [mode, setMode] = useState("");
  const terms = query.trim().toLocaleLowerCase("ru").split(/\s+/).filter(Boolean);
  const filtered = sourceCatalogue.filter(entry => {
    const text = [entry.name, entry.description, entry.connection, entry.url, entry.feedUrl, ...entry.extraUrls].join(" ").toLocaleLowerCase("ru");
    return (!group || entry.group === group) && (!priority || (entry.priority ?? "none") === priority)
      && (!mode || entry.mode === mode) && terms.every(term => text.includes(term));
  });
  const connected = new Map(sources.map(source => [comparableUrl(source.url), source]));

  return <section className="news-stack" aria-label="Каталог источников">
    <div className="admin-filters news-filters news-catalogue-filters">
      <div className="admin-field news-catalogue-search"><label htmlFor="news-catalogue-query">Поиск по названию, адресу и описанию</label><input id="news-catalogue-query" type="search" value={query} onChange={event => setQuery(event.target.value)} maxLength={200} /></div>
      <div className="admin-field"><label htmlFor="news-catalogue-group">Раздел каталога</label><select id="news-catalogue-group" value={group} onChange={event => setGroup(event.target.value)}>
        <option value="">Все разделы</option>{sourceGroups.map(item => <option key={item.id} value={item.id}>{item.title} ({sourceCatalogue.filter(entry => entry.group === item.id).length})</option>)}
      </select></div>
      <div className="admin-field"><label htmlFor="news-catalogue-mode">Способ использования</label><select id="news-catalogue-mode" value={mode} onChange={event => setMode(event.target.value)}>
        <option value="">Все способы</option>{Object.entries(modeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></div>
      <div className="admin-field"><label htmlFor="news-catalogue-priority">Приоритет каталога</label><select id="news-catalogue-priority" value={priority} onChange={event => setPriority(event.target.value)}>
        <option value="">Любой приоритет</option><option value="A">A — в первую очередь</option><option value="B">B — расширение</option><option value="C">C — время от времени</option><option value="none">Не указан</option>
      </select></div>
      <button type="button" className="admin-button" onClick={() => { setQuery(""); setGroup(""); setPriority(""); setMode(""); }}>Сбросить фильтры</button>
    </div>
    <p role="status" className="admin-muted">Показано: {filtered.length} из {sourceCatalogue.length}. Авторы, упомянутые в разных разделах исходного списка, сохранены в каждом из них.</p>
    {filtered.length ? <ul className="news-catalogue-list">{filtered.map(entry => {
      const urls = [...new Set([entry.url, entry.feedUrl, ...entry.extraUrls].filter((url): url is string => !!url))];
      const existing = urls.map(url => connected.get(comparableUrl(url))).find(Boolean);
      const canCollect = entry.mode === "rss" || entry.mode === "auto";
      return <li className="news-catalogue-entry" key={entry.id}>
        <div className="news-stack news-catalogue-copy">
          <div className="news-badges"><span className="admin-muted">{sourceGroups.find(item => item.id === entry.group)?.title}</span><span className="admin-status">{modeLabels[entry.mode]}</span>{entry.priority && <span className="admin-status">Приоритет {entry.priority}</span>}{entry.vendor && <span className="admin-status">Источник поставщика</span>}</div>
          <h2><a className="admin-link" href={entry.url} target="_blank" rel="noopener noreferrer">{entry.name}{" "}<span className="sr-only">(в новой вкладке)</span></a></h2>
          <p>{entry.description}</p>
          <p className="admin-muted"><strong>Подключение из каталога:</strong> {entry.connection}</p>
          <details className="news-catalogue-addresses"><summary>Адреса источника ({urls.length})</summary><ul>{urls.map(url => <li key={url}><a className="admin-link" href={url} target="_blank" rel="noopener noreferrer">{url}{" "}<span className="sr-only">(в новой вкладке)</span></a></li>)}</ul></details>
        </div>
        <div className="news-stack news-catalogue-actions">
          {existing ? <><span className="admin-status">{existing.active ? "Подключён" : "На паузе"}</span><Link className="admin-button" prefetch={false} href={`/admin/news/sources/${existing.slug}`} aria-label={`Настроить источник: ${entry.name}`}>Настроить источник</Link></>
            : canCollect ? <><Link className="admin-button" prefetch={false} href={`/admin/news/sources/new?catalogue=${encodeURIComponent(entry.id)}`} aria-label={`Проверить и подключить: ${entry.name}`}>Проверить и подключить</Link><p className="admin-muted">Сначала предпросмотр, затем сохранение и включение сбора.</p></>
              : <p className="admin-muted">{entry.mode === "api" ? "Подключение этого API пока не поддерживается. Условия доступа и документация — на сайте источника." : "Ресурс для чтения или выбора ленты. Откройте сайт; регулярный сбор здесь не настроен."}</p>}
        </div>
      </li>;
    })}</ul> : <p className="admin-empty">По этим условиям источников нет. Измените запрос или сбросьте фильтры.</p>}
  </section>;
}
