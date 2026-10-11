"use client";

import { useEffect, useId, useRef, useState } from "react";

import { ContentRequestError, listContentImages, uploadContentImage } from "@/lib/admin-api/content-client";
import type { AdminContentImage } from "@/lib/admin-api/types";

const focusableSelector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ContentRequestError ? error.message : fallback;
}

export function ImageInsertDialog({ open, onClose, onInsert }: {
  open: boolean;
  onClose: () => void;
  onInsert: (markdown: string) => void;
}) {
  const titleId = useId();
  const listTitleId = useId();
  const uploadTitleId = useId();
  const fileId = useId();
  const altId = useId();
  const insertAltId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  const [images, setImages] = useState<AdminContentImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [insertAlt, setInsertAlt] = useState("");

  // Reset the form each time the dialog opens (adjust-during-render pattern).
  const [wasOpen, setWasOpen] = useState(open);
  if (wasOpen !== open) {
    setWasOpen(open);
    if (open) {
      setImages([]);
      setLoading(true);
      setLoadError(null);
      setFile(null);
      setAlt("");
      setUploading(false);
      setUploadError(null);
      setSelectedId(null);
      setInsertAlt("");
    }
  }

  useEffect(() => {
    if (!open) return;
    let active = true;
    listContentImages()
      .then((list) => { if (active) setImages(list); })
      .catch((error: unknown) => {
        if (active) setLoadError(errorMessage(error, "Не удалось загрузить список изображений. Попробуйте ещё раз."));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector)).filter((element) => !element.hasAttribute("disabled"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !panel.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [open, onClose]);

  const selectedImage = images.find((image) => image.id === selectedId) ?? null;

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await uploadContentImage(file);
      onInsert(`![${alt}](${uploaded.path})`);
      onClose();
    } catch (error: unknown) {
      setUploadError(errorMessage(error, "Не удалось загрузить изображение. Попробуйте ещё раз."));
    } finally {
      setUploading(false);
    }
  }

  function handleInsertExisting(image: AdminContentImage) {
    onInsert(`![${insertAlt}](${image.path})`);
    onClose();
  }

  if (!open) return null;

  return (
    <div className="editor-dialog-backdrop" onClick={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="editor-dialog editor-image-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId} className="editor-dialog-title">Вставка изображения</h2>

        <section className="editor-image-section" aria-labelledby={uploadTitleId}>
          <h3 id={uploadTitleId} className="editor-image-section-heading">Загрузить новое изображение</h3>
          <div className="admin-field">
            <label htmlFor={fileId}>Файл изображения (JPEG, PNG или WebP)</label>
            <input id={fileId} type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </div>
          <div className="admin-field">
            <label htmlFor={altId}>Альтернативный текст (alt)</label>
            <input id={altId} type="text" value={alt} disabled={uploading} onChange={(event) => setAlt(event.target.value)} placeholder="Описание изображения" />
            <p className="editor-image-hint">Alt обязателен для информативных изображений; оставьте поле пустым только для декоративных.</p>
          </div>
          <div>
            <button type="button" className="admin-button admin-button-primary" onClick={() => void handleUpload()} disabled={!file || uploading} aria-busy={uploading}>
              {uploading ? "Загружаем…" : "Загрузить"}
            </button>
          </div>
        </section>

        {uploadError && <p role="alert" className="admin-error">{uploadError}</p>}

        <section className="editor-image-section" aria-labelledby={listTitleId}>
          <h3 id={listTitleId} className="editor-image-section-heading">Загруженные изображения</h3>
          {loading && <p role="status" className="admin-muted">Загружаем список изображений…</p>}
          {!loading && loadError && <p role="alert" className="admin-error">{loadError}</p>}
          {!loading && !loadError && images.length === 0 && <p className="admin-muted">Загруженных изображений пока нет.</p>}
          {!loading && !loadError && images.length > 0 && (
            <>
              <ul className="editor-image-grid">
                {images.map((image) => (
                  <li key={image.id} className="editor-image-item">
                    <button
                      type="button"
                      className="editor-image-thumb"
                      aria-pressed={selectedId === image.id}
                      aria-label={`Выбрать: ${image.original_name}`}
                      title={image.original_name}
                      onClick={() => { setSelectedId(image.id); setInsertAlt(""); }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element -- admin dialog needs the raw uploaded file, not the image optimizer */}
                      <img src={image.path} alt={image.original_name} loading="lazy" width={image.width} height={image.height} />
                    </button>
                  </li>
                ))}
              </ul>
              {selectedImage && (
                <div className="editor-image-insert-row">
                  <div className="admin-field">
                    <label htmlFor={insertAltId}>Альтернативный текст для «{selectedImage.original_name}»</label>
                    <input id={insertAltId} type="text" value={insertAlt} onChange={(event) => setInsertAlt(event.target.value)} placeholder="Описание изображения" />
                  </div>
                  <button type="button" className="admin-button admin-button-primary" onClick={() => handleInsertExisting(selectedImage)}>Вставить</button>
                </div>
              )}
            </>
          )}
        </section>

        <div className="editor-dialog-actions">
          <button type="button" className="admin-button" ref={cancelRef} onClick={onClose} disabled={uploading}>Отмена</button>
        </div>
      </div>
    </div>
  );
}
