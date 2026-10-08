"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { sourceSuggestions } from "@/lib/news-api/catalogue";
import { externalNewsUrl } from "@/lib/news-api/params";
import type { NewsDiscovery, NewsJobAccepted, NewsSource, NewsTaxonomy } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";
import { discoveryFromJob, NewsDiscoveryPreview, NewsJobProgress } from "./NewsJobProgress";

const selectorFields = [
  ["item_selector", "Блок публикации", "article"],
  ["title_selector", "Заголовок", "h2"],
  ["link_selector", "Ссылка", "a"],
  ["date_selector", "Дата", "time"],
  ["content_selector", "Текст или описание", ".summary"],
] as const;
const fingerprint = (url: string, kind: string, config: Record<string, string>) => JSON.stringify([url.trim(), kind, Object.entries(config).sort(([a], [b]) => a.localeCompare(b))]);

function TaxonomyCheckboxes({ label, name, values, selected, disabled }: { label: string; name: string; values: NewsTaxonomy[]; selected: number[]; disabled: boolean }) {
  return <fieldset className="news-fieldset" disabled={disabled}><legend>{label}</legend>{values.length ? <div className="news-checks">
    {values.map(value => <label className="news-check" key={value.id}><input type="checkbox" name={name} value={value.id} defaultChecked={selected.includes(value.id)} />{value.name}{!value.active ? " (неактивна)" : ""}</label>)}
  </div> : <p className="admin-muted">Пока нет. Добавьте в разделе «Темы и рубрики».</p>}</fieldset>;
}

export function NewsSourceForm({ source, topics, categories }: { source?: NewsSource; topics: NewsTaxonomy[]; categories: NewsTaxonomy[] }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const [name, setName] = useState(source?.name ?? "");
  const [url, setUrl] = useState(source?.url ?? "");
  const [kind, setKind] = useState<"auto" | "rss" | "html">(source?.kind ?? "auto");
  const [selectors, setSelectors] = useState(source?.config ?? {});
  const [vendor, setVendor] = useState(source?.vendor_affiliated ?? false);
  const [checking, setChecking] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [preview, setPreview] = useState<NewsDiscovery | null>(null);
  const [verified, setVerified] = useState<{ key: string; jobId: number } | null>(null);
  const config = kind === "html" ? Object.fromEntries(Object.entries(selectors).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])) : {};
  const key = fingerprint(url, kind, config);
  const unchanged = source && key === fingerprint(source.url, source.kind, source.config);
  const validProof = verified?.key === key;

  async function discover() {
    mutation.setMessage("");
    if (!externalNewsUrl(url.trim()) || new URL(url.trim()).hash) { mutation.setError("Укажите полный адрес источника с http:// или https:// без логина, пароля и фрагмента после #."); return; }
    setVerified(null); setPreview(null);
    const result = await mutation.run<NewsJobAccepted>("/sources/discover", { url: url.trim(), ...(kind !== "auto" ? { kind } : {}), config });
    if (result) { setJobId(result.job_id); setChecking(true); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.setMessage("");
    if (!name.trim() || !externalNewsUrl(url.trim())) { mutation.setError("Заполните название и корректный адрес источника."); return; }
    if (!unchanged && !validProof) { mutation.setError("Сначала проверьте текущий адрес и настройки источника."); return; }
    const data = new FormData(event.currentTarget);
    const result = await mutation.run<NewsSource>(source ? `/sources/${source.id}` : "/sources", {
      name: name.trim(), url: url.trim(), kind, config,
      active: data.has("active"), vendor_affiliated: vendor,
      priority: Number(data.get("priority")), trust_score: Number(data.get("trust_score")), interval_hours: Number(data.get("interval_hours")),
      topic_ids: data.getAll("topic_ids").map(Number), category_ids: data.getAll("category_ids").map(Number),
      ...(validProof ? { discovery_job_id: verified.jobId } : {}),
    }, source ? "PATCH" : "POST");
    if (result) { router.push("/admin/news/sources"); router.refresh(); }
  }

  return <form className="news-form" onSubmit={save} aria-busy={mutation.pending || checking}>
    {!source && <div className="admin-field"><label htmlFor="news-source-suggestion">Подставить адрес из каталога</label><select id="news-source-suggestion" defaultValue="" disabled={checking || mutation.pending} onChange={event => {
      const suggestion = sourceSuggestions[Number(event.target.value)];
      if (!suggestion || !event.target.value) return;
      setName(suggestion.name); setUrl(suggestion.url); setKind(suggestion.kind); setSelectors({}); setVendor(suggestion.vendor); setVerified(null); setPreview(null);
    }}><option value="">Свой источник</option>{sourceSuggestions.map((suggestion, index) => <option value={index} key={suggestion.url}>{suggestion.name}</option>)}</select><p className="admin-muted">Адреса из исследовательского каталога. Каждый источник нужно проверить перед сохранением.</p></div>}
    <div className="news-fields-two">
      <div className="admin-field"><label htmlFor="news-source-name">Название (обязательно)</label><input id="news-source-name" value={name} onChange={event => setName(event.target.value)} maxLength={200} required disabled={mutation.pending} /></div>
      <div className="admin-field"><label htmlFor="news-source-kind">Способ получения</label><select id="news-source-kind" value={kind} onChange={event => setKind(event.target.value as typeof kind)} disabled={checking || mutation.pending}><option value="auto">Определить автоматически</option><option value="rss">RSS / Atom</option><option value="html">HTML</option></select></div>
    </div>
    <div className="admin-field"><label htmlFor="news-source-url">URL источника (обязательно)</label><input id="news-source-url" type="url" value={url} onChange={event => setUrl(event.target.value)} required maxLength={2000} disabled={checking || mutation.pending} autoComplete="url" /></div>
    {kind === "html" && <fieldset className="news-fieldset"><legend>CSS-селекторы для HTML</legend><p className="admin-muted">Укажите селекторы элементов списка публикаций и выполните проверку.</p><div className="news-fields-two">
      {selectorFields.map(([field, label, placeholder]) => <div className="admin-field" key={field}><label htmlFor={`news-${field}`}>{label}</label><input id={`news-${field}`} value={selectors[field] ?? ""} onChange={event => setSelectors(value => ({ ...value, [field]: event.target.value }))} placeholder={placeholder} maxLength={500} disabled={checking || mutation.pending} /></div>)}
    </div></fieldset>}
    <div className="news-stack"><div><button type="button" className="admin-button" onClick={discover} disabled={checking || mutation.pending}>{checking ? "Проверяем источник…" : "Проверить источник"}</button></div>
      {jobId && <NewsJobProgress key={jobId} jobId={jobId} onFinish={job => {
        setChecking(false);
        const result = discoveryFromJob(job);
        if (result) {
          setPreview(result); setUrl(result.url); setKind(result.kind);
          setVerified({ jobId: job.id, key: fingerprint(result.url, result.kind, result.kind === "html" ? config : {}) });
          mutation.setMessage("Проверка завершена. Просмотрите найденные материалы и сохраните источник.");
        }
      }} />}
      {preview && <NewsDiscoveryPreview preview={preview} />}
      {verified && !validProof && <p className="admin-muted">Адрес или селекторы изменены. Повторите проверку.</p>}
    </div>
    <div className="news-fields-three">
      <div className="admin-field"><label htmlFor="news-priority">Приоритет, 0–100</label><input id="news-priority" type="number" name="priority" min={0} max={100} defaultValue={source?.priority ?? 50} required disabled={mutation.pending} /></div>
      <div className="admin-field"><label htmlFor="news-trust">Доверие к источнику, 0–100</label><input id="news-trust" type="number" name="trust_score" min={0} max={100} defaultValue={source?.trust_score ?? 50} required disabled={mutation.pending} /></div>
      <div className="admin-field"><label htmlFor="news-interval">Интервал проверок, часов</label><input id="news-interval" type="number" name="interval_hours" min={1} max={720} defaultValue={source?.interval_hours ?? 6} required disabled={mutation.pending} /></div>
    </div>
    <TaxonomyCheckboxes label="Темы" name="topic_ids" values={topics} selected={source?.topic_ids ?? []} disabled={mutation.pending} />
    <TaxonomyCheckboxes label="Рубрики" name="category_ids" values={categories} selected={source?.category_ids ?? []} disabled={mutation.pending} />
    <label className="news-check"><input type="checkbox" checked={vendor} onChange={event => setVendor(event.target.checked)} disabled={mutation.pending} />Источник связан с поставщиком продукта</label>
    <label className="news-check"><input type="checkbox" name="active" defaultChecked={source?.active ?? false} disabled={mutation.pending} />Включить регулярный сбор</label>
    <NewsFeedback {...mutation} />
    <div className="news-actions"><button className="admin-button admin-button-primary" type="submit" disabled={mutation.pending || checking}>{mutation.pending ? "Сохраняем…" : "Сохранить источник"}</button><p className="admin-muted">{unchanged ? "Адрес и настройки получения не изменены." : validProof ? "Текущий адрес проверен." : "Сохранение доступно после успешной проверки."}</p></div>
  </form>;
}
