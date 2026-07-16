"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchDashboard } from "@/lib/api";
import type { DashboardPayload } from "@/lib/types";
import { InsightBlock } from "@/components/InsightBlock";
import { ReportDataView } from "@/components/ReportDataView";
import { KpiRow } from "@/components/KpiRow";

export default function DashboardPage() {
  const params = useParams();
  const id = String(params?.id || "");
  const [dash, setDash] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchDashboard(id).then((d) => {
      if (!d) setError("Không tìm thấy dashboard.");
      else setDash(d);
    });
  }, [id]);

  if (error) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6 text-ink-soft">
        {error}
      </div>
    );
  }

  if (!dash) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6 text-ink-soft">
        Đang tải dashboard…
      </div>
    );
  }

  return (
    <div className="min-h-dvh px-4 py-8 md:px-8">
      <div className="mb-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal">
          Shared dashboard
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-extrabold text-ink">
          {dash.title}
        </h1>
        <p className="mt-1 text-sm text-ink-soft/70">
          Domain: {dash.domain_id} · {new Date(dash.created_at).toLocaleString("vi-VN")}
        </p>
      </div>

      <div className="grid gap-6">
        {dash.reports.map((r, i) => {
          const labels = r.column_labels || {};
          return (
            <section
              key={i}
              className="overflow-hidden rounded-2xl border border-line bg-white/95 p-5 shadow-sm"
            >
              <h2 className="font-[family-name:var(--font-display)] text-lg font-bold text-ink">
                {r.query}
              </h2>
              {r.insight && (
                <div className="mt-4">
                  <InsightBlock text={r.insight} />
                </div>
              )}
              {r.data?.length > 0 && (
                <div className="mt-4 space-y-4">
                  <KpiRow
                    data={r.data}
                    labels={labels}
                    period={r.period_comparison}
                    forecast={r.forecast}
                  />
                  <ReportDataView
                    data={r.data}
                    chartType={r.chart_type}
                    labels={labels}
                    forecast={r.forecast}
                    query={r.query}
                  />
                </div>
              )}
              {r.chart_image_base64 && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={
                    r.chart_image_base64.startsWith("data:")
                      ? r.chart_image_base64
                      : `data:image/png;base64,${r.chart_image_base64}`
                  }
                  alt="Chart snapshot"
                  className="mt-4 max-h-[320px] w-full rounded-xl border border-line object-contain"
                />
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
