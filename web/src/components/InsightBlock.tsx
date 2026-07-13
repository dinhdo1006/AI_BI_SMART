"use client";

function parseSections(text: string): { title: string; body: string }[] {
  const cleaned = text.replace(/\r\n/g, "\n").trim();
  if (!cleaned) return [];

  const heading = /^(#{1,3}\s+.+|[A-ZÀ-Ỹ][^\n]{0,80}:)\s*$/m;
  const lines = cleaned.split("\n");
  const sections: { title: string; body: string }[] = [];
  let title = "Nhận định";
  let body: string[] = [];

  const flush = () => {
    const b = body.join("\n").trim();
    if (b) sections.push({ title, body: b });
    body = [];
  };

  for (const line of lines) {
    const t = line.trim();
    if (
      /^#{1,3}\s+/.test(t) ||
      (/^[A-ZÀ-Ỹ].{0,60}:$/.test(t) && t.length < 70)
    ) {
      flush();
      title = t.replace(/^#{1,3}\s+/, "").replace(/:$/, "");
      continue;
    }
    if (heading.test(t) && body.length > 2) {
      flush();
      title = t.replace(/:$/, "");
      continue;
    }
    body.push(line);
  }
  flush();

  if (!sections.length) return [{ title: "Nhận định", body: cleaned }];
  return sections.slice(0, 6);
}

export function InsightBlock({ text }: { text: string }) {
  const sections = parseSections(text);

  return (
    <div className="space-y-3">
      {sections.map((s) => (
        <div
          key={s.title + s.body.slice(0, 24)}
          className="rounded-xl border border-line bg-gradient-to-br from-mist/80 to-white px-4 py-3"
        >
          <p className="font-[family-name:var(--font-serif)] text-[1.05rem] font-semibold tracking-tight text-ink">
            {s.title}
          </p>
          <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
            {s.body}
          </p>
        </div>
      ))}
    </div>
  );
}
