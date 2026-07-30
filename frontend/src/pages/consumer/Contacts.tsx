import { FormEvent, useEffect, useState } from "react";
import { Trash2, UserPlus, Users } from "lucide-react";
import { api } from "../../api/client";
import type { TrustedContact } from "../../api/types";

export default function Contacts() {
  const [contacts, setContacts] = useState<TrustedContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setContacts(await api.listContacts());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const c = await api.addContact(name, phone);
      setContacts((prev) => [...prev, c]);
      setName("");
      setPhone("");
    } catch {
      setError("Could not add contact. Check the phone number.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setContacts((prev) => prev.filter((c) => c.id !== id));
    try {
      await api.deleteContact(id);
    } catch {
      load(); // resync if the delete failed
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-black/5 bg-consumer-surface px-4 py-3">
        <h1 className="flex items-center gap-2 font-display text-lg font-bold text-consumer-ink">
          <Users size={20} className="text-consumer-accent" />
          Trusted contacts
        </h1>
        <p className="text-xs text-consumer-muted">
          If a scam is confirmed, these people are alerted so you are never
          isolated.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {loading ? (
          <p className="text-sm text-consumer-muted">Loading…</p>
        ) : contacts.length === 0 ? (
          <div className="mt-6 flex flex-col items-center text-center">
            <Users size={32} className="mb-2 text-gray-300" />
            <p className="text-sm text-consumer-muted">
              No contacts yet. Add a family member below.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {contacts.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded-xl bg-white px-3 py-3 shadow-sm"
              >
                <div>
                  <p className="text-sm font-semibold text-consumer-ink">{c.name}</p>
                  <p className="font-mono text-xs text-consumer-muted">{c.phone}</p>
                </div>
                <button
                  onClick={() => remove(c.id)}
                  className="rounded-lg p-2 text-consumer-muted hover:bg-verdict-danger/10 hover:text-verdict-danger"
                  aria-label={`Remove ${c.name}`}
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <form
        onSubmit={add}
        className="space-y-2 border-t border-black/5 bg-consumer-surface p-3"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          required
          className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone (e.g. +919812345678)"
          required
          className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-consumer-accent"
        />
        {error && (
          <p role="alert" className="text-xs text-verdict-danger">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-consumer-accent py-2.5 font-semibold text-white disabled:opacity-60"
        >
          <UserPlus size={18} /> Add contact
        </button>
      </form>
    </div>
  );
}
