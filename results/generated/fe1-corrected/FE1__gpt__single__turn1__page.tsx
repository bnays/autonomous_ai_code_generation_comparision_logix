'use client';

import { useEffect, useState } from 'react';
import { apiRequest } from '@/lib/api-client';

// Cast to any to avoid strict prop type coupling with existing components
import BudgetComp from '@/components/dashboard/overview/budget';
import TotalCustomersComp from '@/components/dashboard/overview/total-customers';
import TasksProgressComp from '@/components/dashboard/overview/tasks-progress';
import TotalProfitComp from '@/components/dashboard/overview/total-profit';
import SalesComp from '@/components/dashboard/overview/sales';
import TrafficComp from '@/components/dashboard/overview/traffic';
import LatestProductsComp from '@/components/dashboard/overview/latest-products';
import LatestOrdersComp from '@/components/dashboard/overview/latest-orders';

const Budget = BudgetComp as any;
const TotalCustomers = TotalCustomersComp as any;
const TasksProgress = TasksProgressComp as any;
const TotalProfit = TotalProfitComp as any;
const Sales = SalesComp as any;
const Traffic = TrafficComp as any;
const LatestProducts = LatestProductsComp as any;
const LatestOrders = LatestOrdersComp as any;

type DashboardSummary = {
  budget?:
    | number
    | {
        amount?: number;
        difference?: number;
        positive?: boolean;
      };
  totalCustomers?: number;
  tasksProgress?: number;
  totalProfit?: number;
  sales?: any;
  traffic?: any;
  recentProducts?: any[];
  recentTransactions?: any[];
  // fallback keys if API uses different names
  customers?: number;
  tasks?: number;
  profit?: number;
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = (await apiRequest('/dashboard/summary')) as DashboardSummary | null;
        if (cancelled || res === null) return;

        setData({
          ...res,
          recentProducts: res?.recentProducts ?? [],
          recentTransactions: res?.recentTransactions ?? [],
        });
      } catch {
        if (!cancelled) {
          setData({
            recentProducts: [],
            recentTransactions: [],
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  const budgetAmount =
    typeof data?.budget === 'number'
      ? data?.budget
      : (data?.budget as any)?.amount ?? 0;
  const budgetDifference =
    typeof data?.budget === 'object' && data?.budget !== null
      ? (data?.budget as any)?.difference ?? 0
      : 0;
  const budgetPositive =
    typeof data?.budget === 'object' && data?.budget !== null
      ? (data?.budget as any)?.positive ?? budgetDifference >= 0
      : true;

  const totalCustomers = data?.totalCustomers ?? data?.customers ?? 0;
  const tasksProgress = data?.tasksProgress ?? data?.tasks ?? 0;
  const totalProfit = data?.totalProfit ?? data?.profit ?? 0;

  const sales = data?.sales ?? {};
  const traffic = data?.traffic ?? {};
  const recentProducts = data?.recentProducts ?? [];
  const recentTransactions = data?.recentTransactions ?? [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <Budget value={budgetAmount} difference={budgetDifference} positive={budgetPositive} />
        <TotalCustomers value={totalCustomers} />
        <TasksProgress value={tasksProgress} />
        <TotalProfit value={totalProfit} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Sales data={sales} chartSeries={sales?.chartSeries} labels={sales?.labels} />
        <Traffic data={traffic} chartSeries={traffic?.chartSeries} labels={traffic?.labels} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <LatestProducts products={recentProducts} items={recentProducts} />
        <LatestOrders orders={recentTransactions} items={recentTransactions} />
      </div>
    </div>
  );
}
