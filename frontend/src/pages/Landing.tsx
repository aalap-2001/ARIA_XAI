import { Link } from "react-router-dom";

/** The public website. Shown at / to anyone who is not signed in; the only action is signing in. */

const TRACE: { who: string; text: string; tone?: "ok" | "bad" | "wait" }[] = [
  { who: "Tom, support agent", text: "Customer Ava Thompson wants to return order 50817. The tent is unused. Please refund it." },
  { who: "Aria Orchestrator", text: "This changes data, so it goes to Aria Executor. Aria Analyst checks the facts first." },
  { who: "Aria Analyst", text: "Order 50817: 289 GBP, delivered 12 days ago, not final sale. Policy found: returns within 30 days." },
  { who: "Rule engine", text: "return_window passed. not_final_sale passed. item_resellable passed.", tone: "ok" },
  { who: "Sentinel policy", text: "289 GBP is above Tom's approval limit. Escalated to the Reviewer role.", tone: "wait" },
  { who: "Aria Executor", text: "Refund plan ready. Nothing has run. Waiting for Sofia Lindqvist to approve." },
];

/** Photos from Unsplash (free to use under the Unsplash License), stored in public/images so the site works offline.
 *  Sources: photo-1781559818983-c32838ee3d55, photo-1629909613654-28e377c37b09, photo-1565793298595-6a879b1d9492,
 *  photo-1758691737124-05c5bffe46f0 on images.unsplash.com. Each is kept at 600 and 1200 pixels wide. */
const PHOTOS = { shop: "online-shop", clinic: "clinic", freight: "freight-depot", team: "team" };
const photo = (name: string, w: number) => `/images/${name}-${w >= 900 ? 1200 : 600}.webp`;

const BUSINESSES: { id: keyof typeof PHOTOS; alt: string; title: string; text: string }[] = [
  { id: "shop", alt: "A warehouse manager checking orders on a tablet between shelves of stock", title: "An online shop",
    text: "Answers questions about orders and stock, and prepares refunds, store credit and purchase orders for the right person to approve." },
  { id: "clinic", alt: "A bright, modern dental treatment room", title: "A group of clinics",
    text: "Handles cancellations and deposits by the policy, and offers freed appointments to patients on the waiting list." },
  { id: "freight", alt: "Lorries parked in rows at a freight depot, seen from above", title: "A freight company",
    text: "Spots late shipments, works out the credit the contract promises, and only assigns carriers that meet your safety rules." },
];

const AGENTS = [
  ["Aria Orchestrator", "Plans, coordinates and ensures everything follows the rules."],
  ["Aria Analyst", "Reads company data and answers questions."],
  ["Aria Executor", "Makes approved changes to the product."],
  ["Aria Watch", "Monitors activity and suggests improvements."],
];

const LAYERS = [
  ["Cognitive Core", "The model states the facts; soft signals, a gate and hard rules decide, and every verdict can be explained."],
  ["Motivation Engine", "The goals the team works towards, and the product events worth acting on."],
  ["Knowledge Fabric", "Your documents and data, mapped to the things your business works with."],
  ["Swarm Orchestrator", "One orchestrator, three lead agents and the specialists they hand work to."],
  ["Anthropomorphic Interface", "How the team talks: in the app, through the API and in your own product's chat."],
  ["Governance Sentinel", "Risk, owners and approvals for every action, guardrails on every model call, and an audit log that cannot be quietly edited."],
];

const STEPS = [
  ["Tell it about your product", "Describe what you do, upload your policies and manuals, and connect your database. There is nothing to pick from a list."],
  ["Aria XAI works out the rest", "It infers your business, then proposes the agent team, the rules with their sources, and who must approve each kind of change."],
  ["Review, publish, stay in charge", "Edit anything in the Studio, publish, and your team starts working. Every change is approved by a person and recorded."],
];

const wrap = "mx-auto max-w-6xl px-5 sm:px-8";
const lead = "leading-relaxed text-muted";

export default function Landing() {
  return (
    <div className="min-h-full bg-bg text-fg">
      <div className="bg-[linear-gradient(180deg,var(--color-panel)_0%,var(--color-accentsoft)_100%)]">
        <header className={`${wrap} flex items-center justify-between py-5`}>
          <span className="text-[19px] font-semibold tracking-tight">Aria XAI</span>
          <Link to="/login" className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white outline-offset-2 hover:bg-accent2 focus-visible:outline-2 focus-visible:outline-accent dark:text-ink">
            Log in
          </Link>
        </header>

        <section className={`${wrap} grid gap-10 pb-16 pt-6 lg:grid-cols-[1fr_1.05fr] lg:items-center lg:gap-14 lg:pb-20`}>
          <div>
            <h1 className="max-w-[16ch] text-[clamp(2.3rem,5vw,3.9rem)] font-semibold leading-[1.04] tracking-[-0.035em]">
              Your product, run by an AI agent team that follows your rules.
            </h1>
            <p className={`mt-5 max-w-[50ch] text-[17px] ${lead}`}>
              Describe your product, upload your documents and connect your data. Aria XAI builds the agents, the rules and the
              approvals around it. The AI proposes, the rules decide, and a named person approves every change.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a href="#how" className="rounded-lg bg-panel px-5 py-3 text-[15px] font-medium text-fg ring-1 ring-line2 hover:bg-panel2">
                See how it works
              </a>
            </div>
            <ul className="mt-10 grid max-w-md gap-4 border-t border-line2 pt-6 sm:grid-cols-2">
              {[["People approve", "Every change has a named, accountable person"], ["Full audit", "A chained log that cannot be quietly edited"]].map(([t, d]) => (
                <li key={t}><div className="text-[15px] font-semibold text-accent">{t}</div><div className="mt-0.5 text-[13px] leading-snug text-muted">{d}</div></li>
              ))}
            </ul>
          </div>

          <img src={photo(PHOTOS.team, 1200)} srcSet={`${photo(PHOTOS.team, 600)} 600w, ${photo(PHOTOS.team, 1200)} 1200w`} sizes="(min-width: 1024px) 50vw, 100vw"
            alt="A team gathered around a laptop, reviewing work together" fetchPriority="high"
            className="aspect-[4/3] w-full rounded-2xl bg-panel2 object-cover shadow-[0_30px_60px_-30px_rgba(15,34,51,.45)] lg:aspect-[6/5]" />
        </section>
      </div>

      <main>
        <section className="border-y border-line bg-panel">
          <div className={`${wrap} grid gap-8 py-12 lg:grid-cols-[1fr_1.25fr] lg:items-center lg:gap-14`}>
            <div>
              <h2 className="max-w-[22ch] text-[26px] font-semibold tracking-[-0.02em]">See one request go through the team</h2>
              <p className={`mt-2 max-w-[46ch] ${lead}`}>
                A support agent asks for a refund. The agents check the order and the policy, the rules decide, and because the amount is above the agent's limit, a reviewer has to approve it before anything changes.
              </p>
            </div>
            <figure aria-label="Example: a refund request handled by the agent team" className="rounded-2xl bg-bg p-5 text-[14px] ring-1 ring-line sm:p-6">
              <div className="mb-3 flex items-center justify-between border-b border-line pb-3 text-[12.5px]">
                <span className="font-semibold">Live trace: refund request</span>
                <span className="flex items-center gap-1.5 font-medium text-warn"><span className="size-1.5 rounded-full bg-warn" />Waiting for approval</span>
              </div>
              <ol className="space-y-2.5">
                {TRACE.map((t, i) => (
                  <li key={i} className="grid grid-cols-[10px_1fr] gap-3">
                    <span className={`mt-[7px] size-2.5 rounded-full ${t.tone === "ok" ? "bg-ok" : t.tone === "wait" ? "bg-warn" : t.tone === "bad" ? "bg-bad" : "bg-accent/50"}`} />
                    <div>
                      <div className="text-[12.5px] font-medium text-muted">{t.who}</div>
                      <div className="mt-0.5 leading-snug">{t.text}</div>
                    </div>
                  </li>
                ))}
              </ol>
              <figcaption className="mt-3 border-t border-line pt-3 text-[12.5px] text-muted">
                When Sofia approves, she is recorded as accountable, the refund is written to the shop database, and the step is added to the audit log.
              </figcaption>
            </figure>
          </div>
        </section>

        <section>
          <div className={`${wrap} py-12`}>
            <h2 className="max-w-[24ch] text-[26px] font-semibold tracking-[-0.02em]">Built around the business you already run</h2>
            <p className={`mt-2 max-w-[58ch] ${lead}`}>
              Aria XAI learns what your business is from what you give it, so the same platform fits very different work.
            </p>
            <div className="mt-7 grid gap-6 md:grid-cols-3">
              {BUSINESSES.map((b) => (
                <figure key={b.id}>
                  <img src={photo(PHOTOS[b.id], 1200)} srcSet={`${photo(PHOTOS[b.id], 600)} 600w, ${photo(PHOTOS[b.id], 1200)} 1200w`}
                    sizes="(min-width: 768px) 33vw, 100vw" alt={b.alt} loading="lazy" decoding="async"
                    className="aspect-[4/3] w-full rounded-xl bg-panel2 object-cover" />
                  <figcaption className="mt-3">
                    <div className="text-[17px] font-semibold">{b.title}</div>
                    <p className={`mt-1 max-w-[40ch] ${lead}`}>{b.text}</p>
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="scroll-mt-4 border-t border-line">
          <div className={`${wrap} py-12`}>
            <h2 className="text-[26px] font-semibold tracking-[-0.02em]">From your product to a working team in three steps</h2>
            <ol className="mt-7 grid gap-7 md:grid-cols-3">
              {STEPS.map(([title, text], i) => (
                <li key={title}>
                  <div className="text-[38px] font-semibold leading-none tracking-[-0.04em] text-accent">{i + 1}</div>
                  <h3 className="mt-3 text-[17px] font-semibold">{title}</h3>
                  <p className={`mt-1.5 max-w-[42ch] ${lead}`}>{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="bg-panel">
          <div className={`${wrap} grid gap-8 py-12 lg:grid-cols-[1fr_1.4fr]`}>
            <div>
              <h2 className="text-[26px] font-semibold tracking-[-0.02em]">The agent team</h2>
              <p className={`mt-2 max-w-[40ch] ${lead}`}>
                Every request starts and ends with Aria Orchestrator. Each lead agent can hand focused work to specialists that know one part of your business.
              </p>
            </div>
            <dl className="divide-y divide-line">
              {AGENTS.map(([name, text]) => (
                <div key={name} className="grid gap-1 py-3.5 sm:grid-cols-[190px_1fr] sm:gap-6">
                  <dt className="font-semibold text-accent">{name}</dt>
                  <dd className="text-muted">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section>
          <div className={`${wrap} py-12`}>
            <h2 className="text-[26px] font-semibold tracking-[-0.02em]">Six layers, each one yours to see and change</h2>
            <p className={`mt-2 max-w-[60ch] ${lead}`}>
              The framework runs in six layers. In the Studio you can read every rule and guardrail, add or edit records, see whether a person or the system created them, and reset a layer to the original.
            </p>
            <ol className="mt-7 border-t border-line2">
              {LAYERS.map(([name, text], i) => (
                <li key={name} className="grid gap-1 border-b border-line2 py-4 sm:grid-cols-[48px_250px_1fr] sm:items-baseline sm:gap-6">
                  <span className="text-[15px] font-medium tabular-nums text-faint">{String(i + 1).padStart(2, "0")}</span>
                  <span className="text-[18px] font-semibold tracking-[-0.01em]">{name}</span>
                  <span className="max-w-[58ch] text-muted">{text}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="bg-ink text-white">
          <div className={`${wrap} grid gap-8 py-12 md:grid-cols-3`}>
            {[
              ["People stay accountable", "Aria Executor only proposes. The person who approves a plan is recorded as responsible, and anything beyond their authority goes to the owner of that area."],
              ["Rules you can read", "Hard rules come from your own documents, with the page they came from. When a rule blocks an action, the reason is shown in plain words."],
              ["A record that holds", "Every sign-in, change, approval and action is written to a chained audit log, and a kill switch stops risky actions at once."],
            ].map(([t, d]) => (
              <div key={t} className="border-l-2 border-[#4cc3c8] pl-4">
                <h3 className="text-[17px] font-semibold">{t}</h3>
                <p className="mt-1.5 leading-relaxed text-white/70">{d}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className={`${wrap} py-6 text-[13px] text-faint`}>© Aria XAI</footer>
    </div>
  );
}
