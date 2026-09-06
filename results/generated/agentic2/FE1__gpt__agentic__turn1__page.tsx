'use client';

import React from 'react';
import { apiRequest } from '@/lib/api-client';

// Attempt default imports; these components are assumed to exist in the given paths
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
    // could be a simple array of numbers or an array of series objects
    series?: number[] | { name: string; data: number[] }[];
  };
  traffic?: {
    labels?: string[];
    series?: number[];
  };
  recentProducts?: any[];
  recentTransactions?: any[];
};

function formatCurrency(value: number): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return `$${value.toLocaleString()}`;
  }
}

function formatNumber(value: number): string {
  try {
    return new Intl.NumberFormat(undefined, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return String(value);
  }
}

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
        // res can be null if a 401 triggered a redirect; just stop here
        if (res === null) return;
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
        <div className="mb-4 text-sm text-gray-500">Loading dashboard...</div>
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

  const budgetValueNum = data?.budget?.value ?? 0;
  const budgetDiff = data?.budget?.difference ?? 0;

  const customersValueNum = data?.totalCustomers?.value ?? 0;
  const customersDiff = data?.totalCustomers?.difference ?? 0;

  const tasksProgressValue = data?.tasksProgress?.value ?? 0;

  const totalProfitValueNum = data?.totalProfit?.value ?? 0;

  // Normalize sales series to the expected format: [{ name, data }]
  const salesLabels = data?.sales?.labels ?? [];
  let salesSeries: { name: string; data: number[] }[] = [{ name: 'Sales', data: [] }];
  if (Array.isArray(data?.sales?.series)) {
    const series = data?.sales?.series as any[];
    if (series.length > 0 && typeof series[0] === 'number') {
      salesSeries = [{ name: 'Sales', data: series as number[] }];
    } else if (series.length > 0 && typeof series[0] === 'object') {
      salesSeries = series as { name: string; data: number[] }[];
    }
  }

  const trafficLabels = data?.traffic?.labels ?? [];
  const trafficSeries = Array.isArray(data?.traffic?.series) ? (data?.traffic?.series as number[]) : [];

  const products = Array.isArray(data?.recentProducts) ? data!.recentProducts : [];
  const orders = Array.isArray(data?.recentTransactions) ? data!.recentTransactions : [];

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <Budget
          value={formatCurrency(budgetValueNum)}
          difference={budgetDiff}
          positive={budgetDiff >= 0}
        />
        <TotalCustomers
          value={formatNumber(customersValueNum)}
          difference={customersDiff}
          positive={customersDiff >= 0}
        />
        <TasksProgress value={Math.max(0, Math.min(100, tasksProgressValue))} />
        <TotalProfit value={formatCurrency(totalProfitValueNum)} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Sales chartSeries={salesSeries} labels={salesLabels} />
        <Traffic chartSeries={trafficSeries} labels={trafficLabels} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LatestProducts products={products} />
        <LatestOrders orders={orders} />
      </div>
    </div>
  );
}
