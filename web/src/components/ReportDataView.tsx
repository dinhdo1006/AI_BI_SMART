"use client";

import { useMemo, useState } from "react";
import { BarChart3, Info, Table2 } from "lucide-react";
import type { ChartType, ChatResponse, Forecast } from "@/lib/types";
import {
  CHART_TYPE_LABELS,
  explainChartChoice,
  type ChartChoiceExplanation,
} from "@/lib/viz";
import { cn } from "@/lib/utils";
import { DataChart } from "@/components/DataChart";
import { DataTable } from "@/components/DataTable";

type ViewTab = "chart" | "table" | "both";

function formatDataAsOf(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

function ChartExplainBanner({
  explanation,
  templateName,
  onPickChart,
}: {
  explanation: ChartChoiceExplanation;
  templateName?: string | null;
  onPickChart?: (type: ChartType) => void;
}) {
  return (
    <div className="rounded-xl border border-teal/20 bg-teal/[0.06] px-4 py-3">
      <p className="text-sm leading-relaxed text-ink">
        <span className="font-semibold text-teal">{explanation.chartLabel}</span>
        {templateName ? (
          <span className="text-ink-soft"> · mẫu «{templateName}»</span>
        ) : null}
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

function TrustStrip({
  dataAsOf,
  shapeNotes,
  priceSources,
}: {
  dataAsOf?: string | null;
  shapeNotes?: string[];
  priceSources?: string[];
}) {
  const notes = (shapeNotes || []).filter(Boolean);
  const sources = priceSources || [];
  if (!dataAsOf && !notes.length && !sources.length) return null;

  return (
    <div className="flex flex-wrap items-start gap-2 rounded-xl border border-line bg-foam/50 px-3 py-2 text-[12px] text-ink-soft">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal" />
      <div className="min-w-0 flex-1 space-y-1">
        {dataAsOf && (
          <p>
            Số liệu tính đến{" "}
            <span className="font-semibold text-ink">
              {formatDataAsOf(dataAsOf)}
            </span>
          </p>
        )}
        {sources.length > 0 && (
          <p>
            Nguồn giá:{" "}
            <span className="font-semibold text-ink">{sources.join(", ")}</span>
          </p>
        )}
        {notes.map((n) => (
          <p key={n} className="text-copper">
            {n}
          </p>
        ))}
      </div>
    </div>
  );
}

export function ReportDataView({
  data,
  chartType,
  labels,
  forecast,
  query,
  dataAsOf,
  chartTemplate,
  shapeNotes,
  trustMeta,
  onChartReady,
  onChartChange,
}: {
  data: Record<string, unknown>[];
  chartType: ChartType;
  labels?: Record<string, string>;
  forecast?: Forecast | null;
  query?: string;
  dataAsOf?: string | null;
  chartTemplate?: ChatResponse["chart_template"];
  shapeNotes?: string[];
  trustMeta?: ChatResponse["trust_meta"];
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

  const mergedNotes = useMemo(() => {
    const fromPayload = shapeNotes || [];
    const fromTrust = trustMeta?.shape_notes || [];
    return [...new Set([...fromPayload, ...fromTrust])];
  }, [shapeNotes, trustMeta?.shape_notes]);

  if (chartType === "table") {
    return (
      <div className="space-y-3">
        <TrustStrip
          dataAsOf={dataAsOf}
          shapeNotes={mergedNotes}
          priceSources={trustMeta?.price_sources}
        />
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

      <TrustStrip
        dataAsOf={dataAsOf}
        shapeNotes={mergedNotes}
        priceSources={trustMeta?.price_sources}
      />

      {explanation && (
        <ChartExplainBanner
          explanation={explanation}
          templateName={chartTemplate?.name}
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
