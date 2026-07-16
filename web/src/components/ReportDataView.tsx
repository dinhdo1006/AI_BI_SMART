"use client";

import { useMemo, useState } from "react";
import { BarChart3, Table2 } from "lucide-react";
import type { ChartType, Forecast } from "@/lib/types";
import {
  CHART_TYPE_LABELS,
  explainChartChoice,
  type ChartChoiceExplanation,
} from "@/lib/viz";
import { cn } from "@/lib/utils";
import { DataChart } from "@/components/DataChart";
import { DataTable } from "@/components/DataTable";

type ViewTab = "chart" | "table" | "both";

function ChartExplainBanner({
  explanation,
  onPickChart,
}: {
  explanation: ChartChoiceExplanation;
  onPickChart?: (type: ChartType) => void;
}) {
  return (
    <div className="rounded-xl border border-teal/20 bg-teal/[0.06] px-4 py-3">
      <p className="text-sm leading-relaxed text-ink">
        <span className="font-semibold text-teal">{explanation.chartLabel}</span>
        {" — "}
        {explanation.message}
      </p>
      {explanation.alternatives.length > 0 && onPickChart && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wide text-ink-soft/60">
            Thử:
          </span>
          {explanation.alternatives.map((alt) => (
            <button
              key={alt.type}
              type="button"
              onClick={() => onPickChart(alt.type)}
              title={alt.reason}
              className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-xs font-semibold text-ink-soft transition hover:border-teal/35 hover:text-teal"
            >
              {CHART_TYPE_LABELS[alt.type].replace(/^Biểu đồ /, "")}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReportDataView({
  data,
  chartType,
  labels,
  forecast,
  query,
  onChartReady,
  onChartChange,
}: {
  data: Record<string, unknown>[];
  chartType: ChartType;
  labels?: Record<string, string>;
  forecast?: Forecast | null;
  query?: string;
  onChartReady?: (getPng: () => string | null) => void;
  onChartChange?: (type: ChartType) => void;
}) {
  const [tab, setTab] = useState<ViewTab>("both");

  const explanation = useMemo(
    () =>
      chartType !== "table"
        ? explainChartChoice(chartType, data, query ?? "")
        : null,
    [chartType, data, query],
  );

  if (chartType === "table") {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <Table2 className="h-3.5 w-3.5" />
          Số liệu chi tiết
        </div>
        <DataTable data={data} columnLabels={labels} />
      </div>
    );
  }

  const showChart = tab === "both" || tab === "chart";
  const showTable = tab === "both" || tab === "table";

  return (
    <div className="space-y-4">
      <div className="flex gap-1 rounded-xl border border-line bg-foam/50 p-1 lg:hidden">
        {(
          [
            ["both", "Cả hai"],
            ["chart", "Biểu đồ"],
            ["table", "Bảng"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn(
              "flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold transition",
              tab === key
                ? "bg-white text-teal shadow-sm"
                : "text-ink-soft hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {explanation && (
        <ChartExplainBanner
          explanation={explanation}
          onPickChart={onChartChange}
        />
      )}

      <div className={cn("space-y-2", !showChart && "hidden lg:block")}>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <BarChart3 className="h-3.5 w-3.5" />
          Biểu đồ
        </div>
        <div className="min-h-[300px] w-full rounded-xl border border-line bg-white p-1 sm:p-2">
          <DataChart
            data={data}
            chartType={chartType}
            labels={labels}
            forecast={forecast}
            query={query}
            onReady={onChartReady}
          />
        </div>
      </div>

      <div className={cn("space-y-2", !showTable && "hidden lg:block")}>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <Table2 className="h-3.5 w-3.5" />
          Số liệu chi tiết
          <span className="font-normal normal-case tracking-normal text-ink-soft/50">
            · {data.length} dòng
          </span>
        </div>
        <DataTable data={data} columnLabels={labels} />
      </div>
    </div>
  );
}
