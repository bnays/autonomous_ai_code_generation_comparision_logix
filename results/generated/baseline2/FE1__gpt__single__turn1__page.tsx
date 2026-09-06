'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { apiRequest } from '@/lib/api-client';

// Dynamically import dashboard components (typed as any to avoid prop-type coupling)
const Budget = dynamic<any>(() => import('@/components/dashboard/overview/Budget'), { ssr: false });
const TotalCustomers = dynamic<any>(() => import('@/components/dashboard/overview/TotalCustomers'), { ssr: false });
const TasksProgress = dynamic<any>(() => import('@/components/dashboard/overview/TasksProgress'), { ssr: false });
const TotalProfit = dynamic<any>(() => import('@/components/dashboard/overview/TotalProfit'), { ssr: false });
const Sales = dynamic<any>(() => import('@/components/dashboard/overview/Sales'), { ssr: false });
const Traffic = dynamic<any>(() => import('@/components/dashboard/overview/Traffic'), { ssr: false });
const LatestProducts = dynamic<any>(() => import('@/components/dashboard/overview/LatestProducts'), { ssr: false });
const LatestOrders = dynamic<any>(() => import('@/components/dashboard/overview/LatestOrders'), { ssr: false });

type DashboardSummary = {
  budget?: number;
  totalCustomers?: number;
  tasksProgress?: number; // 0-100
  totalProfit?: number;
  sales?: any; // chart data shape handled by Sales component
  traffic?: any; // chart data shape handled by Traffic component
  recentProducts?: any[];
  recentTransactions?: any[];
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiRequest('/dashboard/summary', { method: 'GET' });
      if (res === null) {
        // 401 handled by apiRequest (redirected). Avoid further state updates.
        return;
      }
      const safe: DashboardSummary = {
        ...res,
        recentProducts: Array.isArray(res?.recentProducts) ? res.recentProducts : [],
        recentTransactions: Array.isArray(res?.recentTransactions) ? res.recentTransactions : [],
      };
      setData(safe);
    } catch (e: any) {
      setError(e?.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await apiRequest('/dashboard/summary', { method: 'GET' });
        if (res === null) return; // redirected
        if (!mounted) return;
        const safe: DashboardSummary = {
          ...res,
          recentProducts: Array.isArray(res?.recentProducts) ? res.recentProducts : [],
          recentTransactions: Array.isArray(res?.recentTransactions) ? res.recentTransactions : [],
        };
        setData(safe);
      } catch (e: any) {
        if (!mounted) return;
        setError(e?.message || 'Failed to load dashboard');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ marginBottom: 8 }}>Error: {error}</div>
        <button onClick={load}>Retry</button>
      </div>
    );
  }

  const budget = data?.budget ?? 0;
  const totalCustomers = data?.totalCustomers ?? 0;
  const tasksProgress = data?.tasksProgress ?? 0;
  const totalProfit = data?.totalProfit ?? 0;

  const salesData = data?.sales ?? { labels: [], series: [] };
  const trafficData = data?.traffic ?? { labels: [], series: [] };

  const products = data?.recentProducts ?? [];
  const orders = data?.recentTransactions ?? [];

  return (
    <div style={{ padding: 16 }}>
      {/* KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ gridColumn: 'span 3' }}>
          <Budget value={budget} />
        </div>
        <div style={{ gridColumn: 'span 3' }}>
          <TotalCustomers value={totalCustomers} />
        </div>
        <div style={{ gridColumn: 'span 3' }}>
          <TasksProgress value={tasksProgress} />
        </div>
        <div style={{ gridColumn: 'span 3' }}>
          <TotalProfit value={totalProfit} />
        </div>
      </div>

      {/* Charts */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={{ gridColumn: 'span 8' }}>
          <Sales data={salesData} />
        </div>
        <div style={{ gridColumn: 'span 4' }}>
          <Traffic data={trafficData} />
        </div>
      </div>

      {/* Latest Products and Orders */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
          gap: 16,
        }}
      >
        <div style={{ gridColumn: 'span 6' }}>
          <LatestProducts products={products} />
        </div>
        <div style={{ gridColumn: 'span 6' }}>
          <LatestOrders orders={orders} />
        </div>
      </div>
    </div>
  );
}
