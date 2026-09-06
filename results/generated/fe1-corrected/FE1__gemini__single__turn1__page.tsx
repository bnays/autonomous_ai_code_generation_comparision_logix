'use client';

import { useEffect, useState } from 'react';
import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        const result = await apiRequest('/dashboard/summary');
        if (isMounted && result) {
          setData(result);
        }
      } catch (error) {
        console.error('Error fetching dashboard summary:', error);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchDashboardSummary();

    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 w-full items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const recentProducts = data?.recentProducts ?? [];
  const recentTransactions = data?.recentTransactions ?? data?.latestOrders ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Budget
          diff={data?.budget?.diff}
          trend={data?.budget?.trend}
          sx={{ height: '100%' }}
          value={typeof data?.budget === 'object' ? data?.budget?.value : data?.budget}
        />
        <TotalCustomers
          diff={data?.totalCustomers?.diff}
          trend={data?.totalCustomers?.trend}
          sx={{ height: '100%' }}
          value={
            typeof data?.totalCustomers === 'object'
              ? data?.totalCustomers?.value
              : data?.totalCustomers
          }
        />
        <TasksProgress
          sx={{ height: '100%' }}
          value={
            typeof data?.tasksProgress === 'object'
              ? data?.tasksProgress?.value
              : data?.tasksProgress
          }
        />
        <TotalProfit
          sx={{ height: '100%' }}
          value={
            typeof data?.totalProfit === 'object'
              ? data?.totalProfit?.value
              : data?.totalProfit
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Sales
            chartSeries={data?.sales?.chartSeries ?? data?.salesSeries ?? []}
            sx={{ height: '100%' }}
          />
        </div>
        <div>
          <Traffic
            chartSeries={data?.traffic?.chartSeries ?? data?.trafficSeries ?? []}
            labels={data?.traffic?.labels}
            sx={{ height: '100%' }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div>
          <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
        </div>
        <div className="lg:col-span-2">
          <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
        </div>
      </div>
    </div>
  );
}
