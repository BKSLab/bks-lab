"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { contentRequest, ContentRequestError } from "@/lib/admin-api/content-client";
import type { AdminContentDetail, ContentType } from "@/lib/admin-api/types";
import { CATEGORY_TITLES } from "@/lib/content";
import { EditorPreview } from "./EditorPreview";
import { EditorTabs, type EditorTab } from "./EditorTabs";
import { MarkdownEditor } from "./MarkdownEditor";
import { RevisionList } from "./RevisionList";
import { StatusPanel } from "./StatusPanel";

const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const createLabels: Record<ContentType, string> = {
  article: "Создать статью",
  note: "Создать заметку",
  project: "Создать проект",
};

function dateInputValue(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : "";
}

function parseTags(input: string): string[] {
  return input.split(",").map((tag) => tag.trim()).filter(Boolean);
}

export function ContentEditorForm(props: { mode: "create"; type: ContentType } | { mode: "edit"; item: AdminContentDetail }) {
  const router = useRouter();
  const type = props.mode === "create" ? props.type : props.item.type;
  const item = props.mode === "edit" ? props.item : null;

  const [title, setTitle] = useState(item?.title ?? "");
  const [slug, setSlug] = useState("");
  const [category, setCategory] = useState(item?.category ?? "");
  const [tagsInput, setTagsInput] = useState(item?.tags.join(", ") ?? "");
  const [publishedAt, setPublishedAt] = useState(dateInputValue(item?.published_at ?? null));
  const [excerpt, setExcerpt] = useState(item?.excerpt ?? "");
  const [coverImage, setCoverImage] = useState(item?.cover_image ?? "");
  const [seoTitle, setSeoTitle] = useState(item?.seo_title ?? "");
  const [seoDescription, setSeoDescription] = useState(item?.seo_description ?? "");
  const [ogImage, setOgImage] = useState(item?.og_image ?? "");
  const [relatedSlug, setRelatedSlug] = useState(item?.related_slug ?? "");
  const [featured, setFeatured] = useState(item?.featured ?? false);
  const [sortOrder, setSortOrder] = useState(item?.sort_order != null ? String(item.sort_order) : "");
  const [readingTime, setReadingTime] = useState(item?.reading_time != null ? String(item.reading_time) : "");
  const [markdown, setMarkdown] = useState(item?.content_markdown ?? "");
  const [status, setStatus] = useState(item?.status ?? "draft");
  const [activeTab, setActiveTab] = useState("text");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const errorRef = useRef<HTMLParagraphElement>(null);

  function showError(text: string) {
    setError(text);
    requestAnimationFrame(() => errorRef.current?.focus());
  }

  function validate(): string {
    if (!title.trim()) return "Заполните заголовок материала.";
    if (props.mode === "create") {
      const value = slug.trim();
      if (!value) return "Укажите адрес материала (slug).";
      if (value.length > 200 || !slugPattern.test(value)) return "Адрес (slug): строчные латинские буквы и цифры, разделённые одиночными дефисами, без дефиса в начале и конце (1–200 символов).";
    }
    if (type !== "project" && !publishedAt) return "Укажите дату публикации.";
    if (type === "article") {
      if (!category) return "Выберите категорию статьи.";
      if (!excerpt.trim()) return "Заполните аннотацию статьи.";
      if (!coverImage.trim()) return "Укажите путь к обложке статьи.";
    }
    if (type === "project") {
      if (!excerpt.trim()) return "Заполните аннотацию проекта.";
      if (!coverImage.trim()) return "Укажите путь к обложке проекта.";
      if (!parseTags(tagsInput).length) return "У проекта должен быть хотя бы один тег.";
    }
    return "";
  }

  function buildBody(): Record<string, unknown> {
    const body: Record<string, unknown> = {
      title: title.trim(),
      tags: parseTags(tagsInput),
      content_markdown: markdown,
    };
    if (props.mode === "create") {
      body.type = type;
      body.slug = slug.trim();
      body.draft = true;
    }
    if (type === "article") {
      body.category = category;
      body.published_at = publishedAt;
      body.excerpt = excerpt.trim();
      body.cover_image = coverImage.trim() || null;
      body.seo_title = seoTitle.trim() || null;
      body.seo_description = seoDescription.trim() || null;
      body.og_image = ogImage.trim() || null;
      const override = Number(readingTime);
      body.reading_time = readingTime.trim() && Number.isFinite(override) && override > 0 ? Math.round(override) : null;
    }
    if (type === "note") {
      body.published_at = publishedAt;
      body.related_slug = relatedSlug.trim() || null;
    }
    if (type === "project") {
      body.excerpt = excerpt.trim();
      body.cover_image = coverImage.trim() || null;
      body.featured = featured;
      const order = Number(sortOrder);
      body.sort_order = sortOrder.trim() && Number.isFinite(order) ? Math.round(order) : null;
      if (props.mode === "create") body.status = "active";
    }
    return body;
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const validationError = validate();
    if (validationError) {
      setActiveTab("settings");
      showError(validationError);
      return;
    }
    setPending(true);
    setError("");
    try {
      if (props.mode === "create") {
        const created = await contentRequest<AdminContentDetail>("", { method: "POST", body: buildBody() });
        router.push(`/admin/content/${created.id}/edit`);
        router.refresh();
      } else {
        await contentRequest<AdminContentDetail>(`/${props.item.id}`, { method: "PATCH", body: buildBody() });
        setMessage("Изменения сохранены.");
        router.refresh();
      }
    } catch (reason) {
      showError(reason instanceof ContentRequestError ? reason.message : "Не удалось сохранить материал. Попробуйте снова.");
    } finally {
      setPending(false);
    }
  }

  const settingsContent = (
    <div className="editor-settings">
      <div className="news-fields-two">
        {props.mode === "create" && (
          <div className="admin-field">
            <label htmlFor="editor-slug">Адрес (slug), обязательно</label>
            <input id="editor-slug" value={slug} onChange={(event) => setSlug(event.target.value)} maxLength={200} aria-required="true"
              disabled={pending} aria-describedby="editor-slug-hint" />
            <p className="admin-muted" id="editor-slug-hint">Только строчные латинские буквы и цифры через дефис. После создания адрес изменить нельзя.</p>
          </div>
        )}
        <div className="admin-field">
          <label htmlFor="editor-title">Заголовок, обязательно</label>
          <input id="editor-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} aria-required="true" disabled={pending} />
        </div>
      </div>

      <div className="news-fields-two">
        {type === "article" && (
          <div className="admin-field">
            <label htmlFor="editor-category">Категория, обязательно</label>
            <select id="editor-category" value={category} onChange={(event) => setCategory(event.target.value)} aria-required="true" disabled={pending}>
              <option value="">Не выбрана</option>
              {Object.entries(CATEGORY_TITLES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        )}
        {type !== "project" && (
          <div className="admin-field">
            <label htmlFor="editor-published-at">Дата публикации, обязательно</label>
            <input id="editor-published-at" type="date" value={publishedAt} onChange={(event) => setPublishedAt(event.target.value)} aria-required="true" disabled={pending} />
          </div>
        )}
        {type === "note" && (
          <div className="admin-field">
            <label htmlFor="editor-related-slug">Связанная статья (slug)</label>
            <input id="editor-related-slug" value={relatedSlug} onChange={(event) => setRelatedSlug(event.target.value)} maxLength={200} disabled={pending}
              aria-describedby="editor-related-hint" placeholder="например, 1c-async" />
            <p className="admin-muted" id="editor-related-hint">Необязательно: slug статьи, к которой относится заметка.</p>
          </div>
        )}
        {type === "article" && (
          <div className="admin-field">
            <label htmlFor="editor-reading-time">Время чтения, мин (необязательно)</label>
            <input id="editor-reading-time" type="number" min={1} value={readingTime} onChange={(event) => setReadingTime(event.target.value)} disabled={pending}
              aria-describedby="editor-reading-hint" />
            <p className="admin-muted" id="editor-reading-hint">По умолчанию вычисляется автоматически из объёма текста.</p>
          </div>
        )}
        {type === "project" && (
          <div className="admin-field">
            <label htmlFor="editor-sort-order">Порядок на главной</label>
            <input id="editor-sort-order" type="number" value={sortOrder} onChange={(event) => setSortOrder(event.target.value)} disabled={pending}
              aria-describedby="editor-sort-hint" />
            <p className="admin-muted" id="editor-sort-hint">Меньше значение — выше проект в блоке на главной.</p>
          </div>
        )}
      </div>

      {type !== "note" && (
        <div className="admin-field">
          <label htmlFor="editor-excerpt">Аннотация, обязательно</label>
          <textarea id="editor-excerpt" value={excerpt} onChange={(event) => setExcerpt(event.target.value)} rows={3} aria-required="true" disabled={pending} />
        </div>
      )}

      {type !== "note" && (
        <div className="news-fields-two">
          <div className="admin-field">
            <label htmlFor="editor-cover">Обложка, обязательно</label>
            <input id="editor-cover" value={coverImage} onChange={(event) => setCoverImage(event.target.value)} maxLength={500} aria-required="true" disabled={pending}
              placeholder="/images/articles/example.webp" />
          </div>
          <div className="admin-field">
            <label htmlFor="editor-tags">Теги{type === "project" ? ", обязательно (минимум 1)" : ""}</label>
            <input id="editor-tags" value={tagsInput} onChange={(event) => setTagsInput(event.target.value)} disabled={pending}
              aria-describedby="editor-tags-hint" placeholder="FastAPI, PostgreSQL" />
            <p className="admin-muted" id="editor-tags-hint">Через запятую.</p>
          </div>
        </div>
      )}
      {type === "note" && (
        <div className="admin-field">
          <label htmlFor="editor-tags-note">Теги</label>
          <input id="editor-tags-note" value={tagsInput} onChange={(event) => setTagsInput(event.target.value)} disabled={pending}
            aria-describedby="editor-tags-note-hint" placeholder="FastAPI, PostgreSQL" />
          <p className="admin-muted" id="editor-tags-note-hint">Через запятую, необязательно.</p>
        </div>
      )}

      {type === "project" && (
        <label className="news-check">
          <input type="checkbox" checked={featured} onChange={(event) => setFeatured(event.target.checked)} disabled={pending} />
          Показывать проект на главной
        </label>
      )}

      {type === "article" && (
        <fieldset className="news-fieldset">
          <legend>SEO (необязательно)</legend>
          <p className="admin-muted">По умолчанию используются заголовок и аннотация материала.</p>
          <div className="news-fields-two">
            <div className="admin-field">
              <label htmlFor="editor-seo-title">SEO-заголовок</label>
              <input id="editor-seo-title" value={seoTitle} onChange={(event) => setSeoTitle(event.target.value)} maxLength={300} disabled={pending} />
            </div>
            <div className="admin-field">
              <label htmlFor="editor-seo-description">SEO-описание</label>
              <input id="editor-seo-description" value={seoDescription} onChange={(event) => setSeoDescription(event.target.value)} maxLength={400} disabled={pending} />
            </div>
          </div>
          <div className="admin-field">
            <label htmlFor="editor-og-image">OG-изображение</label>
            <input id="editor-og-image" value={ogImage} onChange={(event) => setOgImage(event.target.value)} maxLength={500} disabled={pending}
              placeholder="/og/bks-lab-default.jpg" />
          </div>
        </fieldset>
      )}
    </div>
  );

  const tabs: EditorTab[] = [
    { key: "text", label: "Текст", content: <MarkdownEditor value={markdown} onChange={setMarkdown} disabled={pending} /> },
    { key: "preview", label: "Предпросмотр", content: <EditorPreview markdown={markdown} /> },
    { key: "settings", label: "Настройки", content: settingsContent },
  ];
  if (item) {
    tabs.push({ key: "revisions", label: "Версии", content: <RevisionList itemId={item.id} /> });
  }

  return (
    <form className="editor-form" onSubmit={save} aria-busy={pending}>
      {item && <StatusPanel item={{ ...item, status }} onChanged={(updated) => { setStatus(updated.status); setMessage("Статус изменён."); router.refresh(); }} />}

      <EditorTabs tabs={tabs} active={activeTab} onChange={setActiveTab} ariaLabel="Разделы редактора" />

      {error && <p className="admin-error news-feedback" role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
      <p className="admin-muted news-feedback" role="status">{pending ? (props.mode === "create" ? "Создаём материал…" : "Сохраняем изменения…") : message}</p>

      <div className="news-actions">
        <button type="submit" className="admin-button admin-button-primary" disabled={pending}>
          {props.mode === "create" ? createLabels[type] : "Сохранить изменения"}
        </button>
        <Link href={item ? `/admin/content/${item.id}` : "/admin/content"} prefetch={false} className="admin-button">
          {item ? "К карточке материала" : "К списку материалов"}
        </Link>
      </div>
    </form>
  );
}
