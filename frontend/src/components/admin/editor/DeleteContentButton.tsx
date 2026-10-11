"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { contentRequest, ContentRequestError } from "@/lib/admin-api/content-client";
import { ConfirmDialog } from "./ConfirmDialog";

export function DeleteContentButton({ itemId, title }: { itemId: number; title: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setPending(true);
    setError("");
    try {
      await contentRequest(`/${itemId}`, { method: "DELETE" });
      router.push("/admin/content");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof ContentRequestError ? reason.message : "Не удалось удалить материал.");
      setPending(false);
    }
  }

  return (
    <>
      <button type="button" className="admin-button admin-button-danger" onClick={() => setOpen(true)}>
        Удалить материал
      </button>
      {error && <p className="admin-error" role="alert">{error}</p>}
      <ConfirmDialog
        open={open}
        title="Удалить материал"
        description={`Материал «${title}» и вся история его версий будут удалены без возможности восстановления.`}
        confirmLabel="Удалить"
        pending={pending}
        onConfirm={remove}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}
