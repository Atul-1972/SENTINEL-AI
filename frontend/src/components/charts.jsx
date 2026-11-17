import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, PieChart as PieIcon } from "lucide-react";
import { EmptyState } from "./ui";
import { number, trafficSeries } from "../lib/format";

const colors = {
  BENIGN: "#68dcb4",
  ATTACK: "#f47f8b",
  LOW: "#68dcb4",
  MEDIUM: "#edbc70",
  HIGH: "#f47f8b",
};
const tooltipStyle = {
  background: "#182130",
  border: "1px solid #334155",
  borderRadius: 9,
  color: "#e8edf5",
  fontSize: 12,
  padding: "10px 14px",
};

export function ActivityChart({ buckets }) {
  const data = trafficSeries(buckets);
  if (!data.length)
    return (
      <EmptyState
        icon={Activity}
        title="Your first analysis starts here"
        description="Submission activity appears after you analyze a traffic file."
      />
    );
  return (
    <div className="activity-chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 18, right: 16, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#68dcb4" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#68dcb4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#253041"
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="hour"
            tick={{ fill: "#8593a7", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            minTickGap={22}
            dy={8}
          />
          <YAxis
            tick={{ fill: "#8593a7", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            itemStyle={{ color: "#68dcb4" }}
            formatter={(value) => [number(value), "Analyzed flows"]}
            labelFormatter={(_, payload) =>
              payload?.[0]
                ? new Date(payload[0].payload.time).toLocaleString()
                : ""
            }
          />
          <Area
            type="monotone"
            dataKey="flows"
            stroke="#68dcb4"
            strokeWidth={2.2}
            fill="url(#activity-fill)"
            isAnimationActive={false}
            activeDot={{
              r: 5,
              fill: "#68dcb4",
              stroke: "#121922",
              strokeWidth: 3,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BreakdownChart({ distribution, total }) {
  const data = Object.entries(distribution || {})
    .map(([name, value]) => ({ name, value }))
    .filter((row) => row.value > 0);
  if (!data.length)
    return (
      <EmptyState
        icon={PieIcon}
        title="No classifications yet"
        description="Run an analysis to populate the breakdown."
      />
    );
  return (
    <>
      <div className="donut-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="64%"
              outerRadius="83%"
              paddingAngle={4}
              cornerRadius={5}
              stroke="none"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {data.map((row) => (
                <Cell key={row.name} fill={colors[row.name]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value) => number(value)}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <strong>{number(total)}</strong>
          <span>Total flows</span>
        </div>
      </div>
      <div className="chart-legend">
        {["BENIGN", "ATTACK"].map((name) => (
          <div key={name}>
            <span>
              <i style={{ background: colors[name] }} />
              {name === "BENIGN" ? "Benign traffic" : "Attack traffic"}
            </span>
            <b className="mono">
              {number(distribution?.[name] || 0)}{" "}
              <small>
                {total
                  ? (((distribution?.[name] || 0) / total) * 100).toFixed(1)
                  : "0"}
                %
              </small>
            </b>
          </div>
        ))}
      </div>
    </>
  );
}

export function RiskDistribution({ distribution }) {
  const total = Object.values(distribution || {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  return (
    <div className="risk-bars">
      {[
        ["HIGH", "High priority"],
        ["MEDIUM", "Needs review"],
        ["LOW", "Low priority"],
      ].map(([level, label]) => (
        <div key={level}>
          <div className="risk-bar-label">
            <span>
              <i style={{ background: colors[level] }} />
              {label}
            </span>
            <b className="mono">{number(distribution?.[level] || 0)}</b>
          </div>
          <div className="risk-track">
            <i
              style={{
                background: colors[level],
                width: `${total ? ((distribution?.[level] || 0) / total) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
