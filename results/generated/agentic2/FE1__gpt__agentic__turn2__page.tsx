'use client';

import React from 'react';
import { apiRequest } from '@/lib/api-client';

import Budget from '@/components/dashboard/overview/budget';
import TotalCustomers from '@/components/dashboard/overview/total-customers';
import TasksProgress from '@/components/dashboard/overview/tasks-progress';
import TotalProfit from '@/components/dashboard/overview/total-profit';
import Sales from '@/components/dashboard/overview/sales';
import Traffic from '@/components/dashboard/overview/traffic';
import LatestProducts from '@/components/dashboard/overview/latest-products';
import LatestOrders from '@/components/dashboard/overview/latest-orders';

type DashboardSummary = {
  budget?: { value?: number; difference?: number };
  totalCustomers?: { value?: number; difference?: number };
  tasksProgress?: { value?: number };
  totalProfit?: { value?: number };
  sales?: {
    labels?: string[];
    series?: number[] | { name: string; data: number[] }[];
  };
  traffic?: {
    labels?: string[];
    series?: number[];
  };
  recentProducts?: any[];
  recentTransactions?: any[];
};

export default function DashboardPage() {
  const [data, setData] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      try {
        const res = await apiRequest('/dashboard/summary', { method: 'GET' });
        if (!active) return;
        if (res === null) return; // 401 handled by apiRequest via redirect
        setData(res as DashboardSummary);
      } catch (err: any) {
        if (!active) return;
        setError(err?.message || 'Failed to load dashboard');
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="p-6">
        <div
          role="progressbar"
          aria-label="Loading dashboard data"
          aria-busy="true"
          className="w-full rounded-md bg-gray-100 p-4 text-sm text-gray-600"
        >
          Loading dashboard data
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  const budgetValue = data?.budget?.value ?? 0;
  const budgetDiff = data?.budget?.difference ?? 0;

  const customersValue = data?.totalCustomers?.value ?? 0;
  const customersDiff = data?.totalCustomers?.difference ?? 0;

  const tasksValue = Math.max(0, Math.min(100, data?.tasksProgress?.value ?? 0));

  const totalProfitValue = data?.totalProfit?.value ?? 0;

  // Normalize sales series to [{ name, data }]
  const salesLabels = data?.sales?.labels ?? [];
  let salesSeries: { name: string; data: number[] }[] = [{ name: 'Sales', data: [] }];
  if (Array.isArray(data?.sales?.series)) {
    const s = data?.sales?.series as any[];
    if (s.length > 0 && typeof s[0] === 'number') {
      salesSeries = [{ name: 'Sales', data: s as number[] }];
    } else if (s.length > 0 && typeof s[0] === 'object') {
      salesSeries = s as { name: string; data: number[] }[];
    }
  }

  const trafficLabels = data?.traffic?.labels ?? [];
  const trafficSeries = Array.isArray(data?.traffic?.series) ? (data?.traffic?.series as number[]) : [];

  const products = Array.isArray(data?.recentProducts) ? data!.recentProducts : [];
  const orders = Array.isArray(data?.recentTransactions) ? data!.recentTransactions : [];

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <Budget value={budgetValue} difference={budgetDiff} positive={budgetDiff >= 0} amount={budgetValue} />
        <TotalCustomers value={customersValue} difference={customersDiff} positive={customersDiff >= 0} />
        <TasksProgress value={tasksValue} />
        <TotalProfit value={totalProfitValue} amount={totalProfitValue} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Sales chartSeries={salesSeries} labels={salesLabels} series={salesSeries} />
        <Traffic chartSeries={trafficSeries} labels={trafficLabels} series={trafficSeries} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LatestProducts products={products} items={products} />
        <LatestOrders orders={orders} rows={orders} transactions={orders} />
      </div>
    </div>
  );
}
