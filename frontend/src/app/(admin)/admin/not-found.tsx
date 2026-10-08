import Link from "next/link";

export default function AdminNotFound() {
  return <div className="admin-state"><h1>Материал не найден</h1><p>Материал удалён или указан неверный адрес.</p><Link className="admin-link" href="/admin/content">К списку материалов</Link></div>;
}
