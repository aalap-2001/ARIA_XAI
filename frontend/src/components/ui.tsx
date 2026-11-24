import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Loader2, X } from "lucide-react";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" | "ok"; size?: "sm" | "md"; loading?: boolean; icon?: ReactNode };
export function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: "bg-accent text-white border-accent hover:bg-accent2",
    secondary: "bg-panel text-fg border-line2 hover:bg-panel2",
    ghost: "bg-transparent border-transparent text-muted hover:bg-panel2 hover:text-fg",
    danger: "bg-panel text-bad border-line2 hover:bg-badsoft",
    ok: "bg-ok text-white border-ok hover:opacity-90",
  }[variant];
  return (
    <button {...p} disabled={disabled || loading}
      className={cx("inline-flex items-center justify-center gap-1.5 rounded-lg border font-medium transition disabled:opacity-50 whitespace-nowrap",
        size === "sm" ? "h-8 px-2.5 text-[13px]" : "h-9 px-3.5 text-sm", v, className)}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export const Card = ({ className, children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) => (
  <div {...p} className={cx("rounded-xl border border-line bg-panel shadow-[0_1px_2px_rgba(16,18,30,.04)]", className)}>{children}</div>
);

export const CardHead = ({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
    <div className="min-w-0"><h2 className="text-[15px] font-semibold">{title}</h2>{sub && <p className="mt-0.5 text-[13px] text-muted">{sub}</p>}</div>
    {right && <div className="flex items-center gap-2">{right}</div>}
  </div>
);

export function Field({ label, hint, error, children }: { label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[13px] font-medium text-fg">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-bad">{error}</span>}
    </label>
  );
}

const inputCls = "w-full rounded-lg border border-line2 bg-panel px-3 text-sm text-fg placeholder:text-faint outline-none focus:border-accent focus:ring-3 focus:ring-accent/20 disabled:opacity-60";
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cx(inputCls, "h-9", p.className)} />;
export const Textarea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={cx(inputCls, "py-2 leading-relaxed", p.className)} />;
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={cx(inputCls, "h-9 pr-8", p.className)} />;

export function Badge({ tone = "neutral", children, className }: { tone?: "neutral" | "ok" | "warn" | "bad" | "info" | "accent"; children: ReactNode; className?: string }) {
  const t = { neutral: "bg-panel2 text-muted border-line", ok: "bg-oksoft text-ok border-transparent", warn: "bg-warnsoft text-warn border-transparent",
    bad: "bg-badsoft text-bad border-transparent", info: "bg-infosoft text-info border-transparent", accent: "bg-accentsoft text-accent border-transparent" }[tone];
  return <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium", t, className)}>{children}</span>;
}

/** Red notification count, 0 to 9, then 9+. Grey when there is nothing waiting. */
export function CountBadge({ n, className }: { n: number; className?: string }) {
  return (
    <span className={cx("inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold leading-none",
      n > 0 ? "bg-bad text-white" : "bg-panel2 text-faint", className)} aria-label={`${n} notification${n === 1 ? "" : "s"}`}>
      {n > 9 ? "9+" : n}
    </span>
  );
}

export const Spinner =({ className }: { className?: string }) => <Loader2 className={cx("size-4 animate-spin text-muted", className)} />;

export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line2 px-6 py-12 text-center">
      {icon && <div className="mb-3 text-faint">{icon}</div>}
      <div className="font-medium">{title}</div>
      {children && <div className="mt-1 max-w-md text-[13px] text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>{sub && <p className="mt-1 max-w-3xl text-[13.5px] text-muted">{sub}</p>}</div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-line scroll-thin">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)} ref={value === t.id ? (el) => { el?.scrollIntoView({ block: "nearest", inline: "nearest" }); } : undefined}
          className={cx("-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm", value === t.id ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg")}>{t.label}</button>
      ))}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={cx("fade-in max-h-[88vh] w-full overflow-y-auto rounded-2xl border border-line bg-panel shadow-2xl scroll-thin", wide ? "max-w-3xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5"><h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-muted hover:bg-panel2" aria-label="Close"><X className="size-4" /></button></div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Alert({ tone = "info", title, children }: { tone?: "info" | "ok" | "warn" | "bad"; title?: ReactNode; children?: ReactNode }) {
  const t = { info: "bg-infosoft text-info", ok: "bg-oksoft text-ok", warn: "bg-warnsoft text-warn", bad: "bg-badsoft text-bad" }[tone];
  return <div className={cx("rounded-lg px-3.5 py-2.5 text-[13px]", t)}>{title && <div className="font-semibold">{title}</div>}{children && <div className={title ? "mt-0.5" : ""}>{children}</div>}</div>;
}

// ------------------------------------------------------------------ toasts
type Toast = { id: number; text: string; tone: "ok" | "bad" };
const ToastCtx = createContext<(text: string, tone?: "ok" | "bad") => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: "ok" | "bad" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), tone === "bad" ? 6500 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} className={cx("fade-in max-w-sm rounded-lg px-4 py-2.5 text-sm shadow-lg", t.tone === "bad" ? "bg-bad text-white" : "bg-fg text-bg")}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

export function Copy({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return <Button size="sm" onClick={() => { navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}>{done ? "Copied" : label}</Button>;
}

/** A credential (key, secret, invite link). Hidden by default; the person chooses to show it. Copy works while hidden. */
export function Secret({ value, onReveal }: { value: string; onReveal?: () => Promise<string> }) {
  const [shown, setShown] = useState(false);
  const [real, setReal] = useState(value);
  useEffect(() => { setReal(value); setShown(false); }, [value]);
  const masked = !real || real.includes("•");
  const toggle = async () => {
    if (!shown && masked && onReveal) setReal(await onReveal());
    setShown(!shown);
  };
  return (
    <div className="flex gap-2">
      <input readOnly aria-label="Hidden value" value={shown ? real : "•".repeat(24)} type={shown ? "text" : "password"}
        className="h-9 w-full min-w-0 rounded-lg border border-line2 bg-panel2 px-3 font-mono text-xs text-fg outline-none" />
      <Button size="sm" onClick={toggle}>{shown ? "Hide" : "Show"}</Button>
      {!masked && <Copy text={real} />}
    </div>
  );
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const run = useCallback(async () => {
    setLoading(true);
    try { setData(await fn()); setError(null); } catch (e: any) { setError(e.message); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

export const Loading = () => <div className="flex items-center gap-2 p-8 text-muted"><Spinner /> Loading…</div>;
export const ErrorBox = ({ error }: { error: string }) => <Alert tone="bad" title="Something went wrong">{error}</Alert>;

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cx("relative h-5 w-9 rounded-full transition", checked ? "bg-accent" : "bg-line2")}>
        <span className={cx("absolute top-0.5 size-4 rounded-full bg-white shadow transition", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      {label}
    </label>
  );
}
