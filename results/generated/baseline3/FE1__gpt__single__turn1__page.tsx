"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { apiRequest } from "@/lib/api-client";

type DashboardSummary = {
  budget?: any;
  totalCustomers?: any;
  tasksProgress?: any;
  totalProfit?: any;
  sales?: any;
  traffic?: any;
  recentProducts?: any[];
  recentTransactions?: any[];
};

// Dynamically import dashboard components (typed as any to avoid prop type coupling)
const Budget = dynamic(() => import("@/components/dashboard/overview/budget"), {
  ssr: false,
}) as any;
const TotalCustomers = dynamic(
  () => import("@/components/dashboard/overview/total-customers"),
  { ssr: false }
) as any;
const TasksProgress = dynamic(
  () => import("@/components/dashboard/overview/tasks-progress"),
  { ssr: false }
) as any;
const TotalProfit = dynamic(
  () => import("@/components/dashboard/overview/total-profit"),
  { ssr: false }
) as any;

const Sales = dynamic(() => import("@/components/dashboard/overview/sales"), {
  ssr: false,
}) as any;
const Traffic = dynamic(
  () => import("@/components/dashboard/overview/traffic"),
  { ssr: false }
) as any;

const LatestProducts = dynamic(
  () => import("@/components/dashboard/overview/latest-products"),
  { ssr: false }
) as any;
const LatestOrders = dynamic(
  () => import("@/components/dashboard/overview/latest-orders"),
  { ssr: false }
) as any;

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      try {
        const res = await apiRequest("/dashboard/summary");
        if (!mounted) return;

        // Ensure optional arrays default to empty to avoid crashes
        const safe: DashboardSummary = {
          ...(res || {}),
          recentProducts: (res?.recentProducts ?? []) as any[],
          recentTransactions: (res?.recentTransactions ?? []) as any[],
        };

        setSummary(safe);
      } catch (e: any) {
        if (!mounted) return;
        setError(e?.message || "Failed to load dashboard");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        <div>Loading dashboard…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, color: "#b91c1c" }}>
        Failed to load dashboard: {error}
      </div>
    );
  }

  // Fallbacks to keep rendering stable
  const data = summary || {
    recentProducts: [],
    recentTransactions: [],
  };

  return (
    <div style={{ padding: 24 }}>
      {/* KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, 1fr)",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ gridColumn: "span 3" }}>
          <Budget {...(data.budget ?? {})} />
        </div>
        <div style={{ gridColumn: "span 3" }}>
          <TotalCustomers {...(data.totalCustomers ?? {})} />
        </div>
        <div style={{ gridColumn: "span 3" }}>
          <TasksProgress {...(data.tasksProgress ?? {})} />
        </div>
        <div style={{ gridColumn: "span 3" }}>
          <TotalProfit {...(data.totalProfit ?? {})} />
        </div>
      </div>

      {/* Charts */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, 1fr)",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ gridColumn: "span 8" }}>
          <Sales {...(data.sales ?? {})} />
        </div>
        <div style={{ gridColumn: "span 4" }}>
          <Traffic {...(data.traffic ?? {})} />
        </div>
      </div>

      {/* Latest Products / Orders */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, 1fr)",
          gap: 16,
        }}
      >
        <div style={{ gridColumn: "span 6" }}>
          <LatestProducts
            products={(data.recentProducts ?? []) as any[]}
            items={(data.recentProducts ?? []) as any[]}
            data={(data.recentProducts ?? []) as any[]}
          />
        </div>
        <div style={{ gridColumn: "span 6" }}>
          <LatestOrders
            orders={(data.recentTransactions ?? []) as any[]}
            items={(data.recentTransactions ?? []) as any[]}
            data={(data.recentTransactions ?? []) as any[]}
          />
        </div>
      </div>
    </div>
  );
}
