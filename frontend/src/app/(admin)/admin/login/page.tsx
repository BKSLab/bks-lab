import type { Metadata } from "next";
import { AdminLoginForm } from "@/components/admin/AdminLoginForm";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Вход" };

export default function AdminLoginPage() {
  return (
    <section className="admin-login" aria-labelledby="admin-login-title">
      <h1 id="admin-login-title">Вход в панель</h1>
      <p className="admin-muted">Статистика сайта, материалы и подписчики.</p>
      <AdminLoginForm />
    </section>
  );
}
