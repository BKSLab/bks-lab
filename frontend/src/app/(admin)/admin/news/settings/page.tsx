import type { Metadata } from "next";
import { NewsSettingsForm } from "@/components/admin/news/NewsSettingsForm";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsSettings } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Настройки редакционного центра" };

export default async function NewsSettingsPage() {
  const user = await requireAdmin();
  const settings = await adminFetch<NewsSettings>("/news/settings");
  return <NewsShell username={user.username} current="settings" title="Настройки анализа" description="Редакционная политика, расписание сбора и критерии рейтинга."><NewsSettingsForm settings={settings} /></NewsShell>;
}
