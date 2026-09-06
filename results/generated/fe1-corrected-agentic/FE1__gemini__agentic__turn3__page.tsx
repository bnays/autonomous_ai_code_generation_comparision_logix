'use client';

import { useEffect, useState } from 'react';
import { Box, Container, CircularProgress } from '@mui/material';
import Grid from '@mui/material/Unstable_Grid2';
import { apiRequest } from '@/lib/api-client';

import * as BudgetModule from '@/components/dashboard/overview/budget';
import * as TotalCustomersModule from '@/components/dashboard/overview/total-customers';
import * as TasksProgressModule from '@/components/dashboard/overview/tasks-progress';
import * as TotalProfitModule from '@/components/dashboard/overview/total-profit';
import * as SalesModule from '@/components/dashboard/overview/sales';
import * as TrafficModule from '@/components/dashboard/overview/traffic';
import * as LatestProductsModule from '@/components/dashboard/overview/latest-products';
import * as LatestOrdersModule from '@/components/dashboard/overview/latest-orders';

const Budget = BudgetModule.Budget || BudgetModule.default;
const TotalCustomers = TotalCustomersModule.TotalCustomers || TotalCustomersModule.default;
const TasksProgress = TasksProgressModule.TasksProgress || TasksProgressModule.default;
const TotalProfit = TotalProfitModule.TotalProfit || TotalProfitModule.default;
const Sales = SalesModule.Sales || SalesModule.default;
const Traffic = TrafficModule.Traffic || TrafficModule.default;
const LatestProducts = LatestProductsModule.LatestProducts || LatestProductsModule.default;
const LatestOrders = LatestOrdersModule.LatestOrders || LatestOrdersModule.default;

interface DashboardSummary {
  budget?: string | number;
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  salesSeries?: any[];
  salesChartSeries?: any[];
  trafficSeries?: any[];
  recentProducts?: any[];
  recentTransactions?: any[];
  recentOrders?: any[];
  [key: string]: any;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted && data) {
          setSummary(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
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
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
        }}
      >
        <CircularProgress aria-label="Loading dashboard data" />
      </Box>
    );
  }

  const recentProducts = summary?.recentProducts ?? [];
  const recentTransactions = summary?.recentTransactions ?? summary?.recentOrders ?? [];

  return (
    <Box component="main" sx={{ flexGrow: 1, py: 8 }}>
      <Container maxWidth="xl">
        <Grid container spacing={3}>
          <Grid xs={12} sm={6} lg={3}>
            <Budget diff={12} trend="up" sx={{ height: '100%' }} value={summary?.budget ?? '$24k'} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalCustomers diff={16} trend="down" sx={{ height: '100%' }} value={summary?.totalCustomers ?? '1.6k'} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TasksProgress sx={{ height: '100%' }} value={summary?.tasksProgress ?? 75.5} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalProfit sx={{ height: '100%' }} value={summary?.totalProfit ?? '$15k'} />
          </Grid>
          <Grid xs={12} lg={8}>
            <Sales
              chartSeries={
                summary?.salesChartSeries ||
                summary?.salesSeries || [
                  { name: 'This year', data: [18, 16, 5, 8, 3, 14, 14, 16, 17, 19, 18, 20] },
                  { name: 'Last year', data: [12, 11, 4, 6, 2, 9, 9, 10, 11, 12, 13, 13] },
                ]
              }
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <Traffic
              chartSeries={summary?.trafficSeries || [63, 15, 22]}
              labels={summary?.trafficLabels || ['Desktop', 'Tablet', 'Phone']}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
          </Grid>
          <Grid xs={12} md={12} lg={8}>
            <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
