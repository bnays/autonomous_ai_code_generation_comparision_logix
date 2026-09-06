'use client';

import React from 'react';
import { apiRequest } from '@/lib/api-client';

// Import dashboard UI components if they exist.
// Some projects export these components as default, others as named.
// We'll default-import and safely render them with fallbacks if undefined.
import BudgetComponent from '@/components/dashboard/overview/budget';
import TotalCustomersComponent from '@/components/dashboard/overview/total-customers';
import TasksProgressComponent from '@/components/dashboard/overview/tasks-progress';
import TotalProfitComponent from '@/components/dashboard/overview/total-profit';
import SalesComponent from '@/components/dashboard/overview/sales';
import TrafficComponent from '@/components/dashboard/overview/traffic';
import LatestProductsComponent from '@/components/dashboard/overview/latest-products';
import LatestOrdersComponent from '@/components/dashboard/overview/latest-orders';

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

function isRenderableComponent(mod: any) {
  return !!mod && (typeof mod === 'function' || (typeof mod === 'object' && '$$typeof' in mod));
}

export default function DashboardPage() {
  const [data, setData] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      try {
        // Tests expect this helper to be called with just the endpoint (no options object).
        const res = await apiRequest('/dashboard/summary');
        if (!active) return;
        if (res === null) return; // 401 handled by apiRequest (token cleared + redirect)
        const payload = (res && typeof res === 'object' && 'data' in res) ? (res as any).data : res;
        setData(payload as DashboardSummary);
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

  // Fallback UIs in case the imported components are not available.
  const FallbackBudget = (
    <div className="rounded-lg border p-4">
      <div className="text-sm text-gray-500">Budget</div>
      <div className="text-xl font-semibold">{budgetValue}</div>
      <div className={`text-xs ${budgetDiff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
        {budgetDiff >= 0 ? '+' : ''}{budgetDiff}%
      </div>
    </div>
  );

  const FallbackTotalCustomers = (
    <div className="rounded-lg border p-4">
      <div className="text-sm text-gray-500">Total Customers</div>
      <div className="text-xl font-semibold">{customersValue}</div>
      <div className={`text-xs ${customersDiff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
        {customersDiff >= 0 ? '+' : ''}{customersDiff}%
      </div>
    </div>
  );

  const FallbackTasksProgress = (
    <div className="rounded-lg border p-4">
      <div className="text-sm text-gray-500">Tasks Progress</div>
      <div className="text-xl font-semibold">{tasksValue}%</div>
    </div>
  );

  const FallbackTotalProfit = (
    <div className="rounded-lg border p-4">
      <div className="text-sm text-gray-500">Total Profit</div>
      <div className="text-xl font-semibold">{totalProfitValue}</div>
    </div>
  );

  const FallbackSales = (
    <section className="rounded-lg border p-4">
      <h2 className="text-base font-semibold">Sales</h2>
      <div className="text-sm text-gray-500">Chart unavailable</div>
    </section>
  );

  const FallbackTraffic = (
    <section className="rounded-lg border p-4">
      <h2 className="text-base font-semibold">Traffic</h2>
      <div className="text-sm text-gray-500">Chart unavailable</div>
    </section>
  );

  const FallbackLatestProducts = (
    <section className="rounded-lg border p-4">
      <h2 className="text-base font-semibold">Latest Products</h2>
      {products.length === 0 ? (
        <p className="text-sm text-gray-500">No recent stock additions found.</p>
      ) : (
        <ul className="mt-2 list-disc pl-5 text-sm">
          {products.map((p, idx) => (
            <li key={p?.id ?? idx}>{p?.name ?? 'Unnamed product'}</li>
          ))}
        </ul>
      )}
    </section>
  );

  const FallbackLatestOrders = (
    <section className="rounded-lg border p-4">
      <h2 className="text-base font-semibold">Latest Orders</h2>
      <div className="overflow-x-auto">
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr>
              <th>Order</th>
              <th>Customer</th>
              <th>Total</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o, idx) => (
              <tr key={o?.id ?? idx}>
                <td>{o?.id ?? '-'}</td>
                <td>{o?.customer ?? '-'}</td>
                <td>{o?.total ?? '-'}</td>
                <td>{o?.status ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );

  // Compose safe renders with fallbacks
  const BudgetEl = isRenderableComponent(BudgetComponent)
    ? React.createElement(BudgetComponent as any, {
        value: budgetValue,
        difference: budgetDiff,
        positive: budgetDiff >= 0,
      })
    : FallbackBudget;

  const TotalCustomersEl = isRenderableComponent(TotalCustomersComponent)
    ? React.createElement(TotalCustomersComponent as any, {
        value: customersValue,
        difference: customersDiff,
        positive: customersDiff >= 0,
      })
    : FallbackTotalCustomers;

  const TasksProgressEl = isRenderableComponent(TasksProgressComponent)
    ? React.createElement(TasksProgressComponent as any, {
        value: tasksValue,
      })
    : FallbackTasksProgress;

  const TotalProfitEl = isRenderableComponent(TotalProfitComponent)
    ? React.createElement(TotalProfitComponent as any, {
        value: totalProfitValue,
      })
    : FallbackTotalProfit;

  const SalesEl = isRenderableComponent(SalesComponent)
    ? React.createElement(SalesComponent as any, {
        chartSeries: salesSeries,
        series: salesSeries,
        labels: salesLabels,
      })
    : FallbackSales;

  const TrafficEl = isRenderableComponent(TrafficComponent)
    ? React.createElement(TrafficComponent as any, {
        chartSeries: trafficSeries,
        series: trafficSeries,
        labels: trafficLabels,
      })
    : FallbackTraffic;

  const LatestProductsEl = isRenderableComponent(LatestProductsComponent)
    ? React.createElement(LatestProductsComponent as any, {
        products,
        items: products,
        data: products,
      })
    : FallbackLatestProducts;

  const LatestOrdersEl = isRenderableComponent(LatestOrdersComponent)
    ? React.createElement(LatestOrdersComponent as any, {
        orders,
        rows: orders,
        transactions: orders,
        data: orders,
      })
    : FallbackLatestOrders;

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
        {BudgetEl}
        {TotalCustomersEl}
        {TasksProgressEl}
        {TotalProfitEl}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {SalesEl}
        {TrafficEl}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {LatestProductsEl}
        {LatestOrdersEl}
      </div>
    </div>
  );
}
