'use client';

import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Unstable_Grid2';

import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { Sales } from '@/components/dashboard/overview/sales';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Traffic } from '@/components/dashboard/overview/traffic';

export default function DashboardPage() {
  const [summaryData, setSummaryData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setIsLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted) {
          setSummaryData(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchDashboardSummary();

    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
          width: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const recentProducts = summaryData?.recentProducts ?? summaryData?.products ?? [];
  const recentTransactions = summaryData?.recentTransactions ?? summaryData?.recentOrders ?? summaryData?.orders ?? [];

  const budgetDiff = summaryData?.budget?.diff;
  const budgetTrend = summaryData?.budget?.trend;
  const budgetValue =
    typeof summaryData?.budget === 'object'
      ? summaryData?.budget?.value ?? '$0'
      : summaryData?.budget ?? '$0';

  const totalCustomersDiff = summaryData?.totalCustomers?.diff;
  const totalCustomersTrend = summaryData?.totalCustomers?.trend;
  const totalCustomersValue =
    typeof summaryData?.totalCustomers === 'object'
      ? summaryData?.totalCustomers?.value ?? '0'
      : summaryData?.totalCustomers ?? '0';

  const tasksProgressValue =
    typeof summaryData?.tasksProgress === 'object'
      ? summaryData?.tasksProgress?.value ?? 0
      : summaryData?.tasksProgress ?? 0;

  const totalProfitValue =
    typeof summaryData?.totalProfit === 'object'
      ? summaryData?.totalProfit?.value ?? '$0'
      : summaryData?.totalProfit ?? '$0';

  const salesSeries =
    summaryData?.sales?.chartSeries ?? summaryData?.salesSeries ?? summaryData?.sales ?? [];
  const trafficSeries =
    summaryData?.traffic?.chartSeries ?? summaryData?.trafficSeries ?? summaryData?.traffic ?? [];
  const trafficLabels =
    summaryData?.traffic?.labels ?? summaryData?.trafficLabels ?? ['Desktop', 'Tablet', 'Phone'];

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Grid container spacing={3}>
        <Grid xs={12} sm={6} lg={3}>
          <Budget
            diff={budgetDiff}
            trend={budgetTrend}
            value={budgetValue}
            sx={{ height: '100%' }}
          />
        </Grid>
        <Grid xs={12} sm={6} lg={3}>
          <TotalCustomers
            diff={totalCustomersDiff}
            trend={totalCustomersTrend}
            value={totalCustomersValue}
            sx={{ height: '100%' }}
          />
        </Grid>
        <Grid xs={12} sm={6} lg={3}>
          <TasksProgress value={tasksProgressValue} sx={{ height: '100%' }} />
        </Grid>
        <Grid xs={12} sm={6} lg={3}>
          <TotalProfit value={totalProfitValue} sx={{ height: '100%' }} />
        </Grid>
        <Grid xs={12} lg={8}>
          <Sales chartSeries={salesSeries} sx={{ height: '100%' }} />
        </Grid>
        <Grid xs={12} md={6} lg={4}>
          <Traffic chartSeries={trafficSeries} labels={trafficLabels} sx={{ height: '100%' }} />
        </Grid>
        <Grid xs={12} md={6} lg={4}>
          <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
        </Grid>
        <Grid xs={12} md={12} lg={8}>
          <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
        </Grid>
      </Grid>
    </Container>
  );
}
