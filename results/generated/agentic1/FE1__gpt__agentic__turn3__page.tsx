'use client';

import React from 'react';
import { apiRequest } from '../../lib/api-client';

// Overview KPI cards
import { Budget } from '../../components/dashboard/overview/budget';
import { TotalCustomers } from '../../components/dashboard/overview/total-customers';
import { TasksProgress } from '../../components/dashboard/overview/tasks-progress';
import { TotalProfit } from '../../components/dashboard/overview/total-profit';

// Charts
import { Sales } from '../../components/dashboard/overview/sales';
import { Traffic } from '../../components/dashboard/overview/traffic';

// Tables (located under overview in this project)
import { LatestProducts } from '../../components/dashboard/overview/latest-products';
import { LatestOrders } from '../../components/dashboard/overview/latest-orders';

type Product = any;
type Order = any;

interface DashboardSummary {
  recentProducts?: Product[];
  recentTransactions?: Order[];
}

export default function DashboardPage() {
  const [data, setData] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;

    (async () => {
      try {
        const res = await apiRequest('/dashboard/summary');
        if (!active) return;
        setData((res as DashboardSummary) ?? {});
      } catch (e: any) {
        if (!active) return;
        setError(e?.message || 'Failed to load dashboard');
        setData({});
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const products = data?.recentProducts ?? [];
  const orders = data?.recentTransactions ?? [];

  // Loosen types for components whose prop types aren't available here
  const BudgetCard = Budget as unknown as React.ComponentType<any>;
  const TotalCustomersCard = TotalCustomers as unknown as React.ComponentType<any>;
  const TasksProgressCard = TasksProgress as unknown as React.ComponentType<any>;
  const TotalProfitCard = TotalProfit as unknown as React.ComponentType<any>;
  const SalesChart = Sales as unknown as React.ComponentType<any>;
  const TrafficChart = Traffic as unknown as React.ComponentType<any>;
  const LatestProductsTable = LatestProducts as unknown as React.ComponentType<{ products: any[] }>;
  const LatestOrdersTable = LatestOrders as unknown as React.ComponentType<{ orders: any[] }>;

  if (loading) {
    return (
      <div className="p-6">
        <div>Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <BudgetCard />
        <TotalCustomersCard />
        <TasksProgressCard />
        <TotalProfitCard />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SalesChart />
        <TrafficChart />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <LatestProductsTable products={products} />
        <LatestOrdersTable orders={orders} />
      </div>
    </div>
  );
}
