'use client';

import React, { useEffect, useState } from 'react';
import { apiRequest } from '@/lib/api-client';

// Overview KPI cards
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';

// Charts
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';

// Tables
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

type DashboardSummary = {
  budget?: { value?: any; difference?: number; positive?: boolean; [key: string]: any };
  totalCustomers?: { value?: any; [key: string]: any };
  tasksProgress?: { value?: any; [key: string]: any };
  totalProfit?: { value?: any; [key: string]: any };
  sales?: Record<string, unknown>;
  traffic?: Record<string, unknown>;
  recentProducts?: any[];
  recentTransactions?: any[];
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const fetchSummary = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiRequest('/dashboard/summary');
        if (!active) return;

        if (res === null) {
          // apiRequest handles 401 by redirecting; stop here
          setLoading(false);
          return;
        }

        const normalized: DashboardSummary = {
          ...res,
          recentProducts: Array.isArray(res?.recentProducts) ? res.recentProducts : [],
          recentTransactions: Array.isArray(res?.recentTransactions) ? res.recentTransactions : [],
        };

        setData(normalized);
      } catch (e: any) {
        if (!active) return;
        setError(e?.message || 'Failed to load dashboard');
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchSummary();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div role="progressbar" aria-label="Loading dashboard data" aria-busy="true">
          Loading dashboard data
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 16 }}>
        Failed to load dashboard: {error}
      </div>
    );
  }

  const budget = (data?.budget ?? {}) as any;
  const totalCustomers = (data?.totalCustomers ?? {}) as any;
  const tasksProgress = (data?.tasksProgress ?? {}) as any;
  const totalProfit = (data?.totalProfit ?? {}) as any;

  const recentProducts = data?.recentProducts ?? [];
  const recentTransactions = data?.recentTransactions ?? [];

  return (
    <div className="dashboard-container" style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: 16 }}>
      <div className="kpi-grid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
        <Budget value={budget.value ?? ''} difference={budget.difference} positive={budget.positive} />
        <TotalCustomers value={totalCustomers.value ?? 0} />
        <TasksProgress value={typeof tasksProgress.value === 'number' ? tasksProgress.value : Number(tasksProgress.value ?? 0)} />
        <TotalProfit value={totalProfit.value ?? ''} />
      </div>

      <div className="charts-grid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
        <Sales {...(((data?.sales ?? {}) as any))} />
        <Traffic {...(((data?.traffic ?? {}) as any))} />
      </div>

      <div className="tables-grid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}>
        <LatestProducts {...(({ products: recentProducts } as any))} />
        <LatestOrders {...(({ orders: recentTransactions } as any))} />
      </div>
    </div>
  );
}
