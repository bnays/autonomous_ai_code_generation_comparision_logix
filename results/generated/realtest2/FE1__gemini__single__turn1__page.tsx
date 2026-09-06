'use client';

import { useEffect, useState } from 'react';
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

export default function Page() {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function fetchSummary() {
      try {
        const data = await apiRequest('/dashboard/summary');
        setSummary(data);
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchSummary();
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
        <CircularProgress />
      </Box>
    );
  }

  const products = summary?.recentProducts ?? summary?.latestProducts ?? summary?.products ?? [];
  const orders = summary?.recentTransactions ?? summary?.latestOrders ?? summary?.orders ?? [];

  return (
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 8,
      }}
    >
      <Container maxWidth="xl">
        <Grid container spacing={3}>
          <Grid xs={12} sm={6} lg={3}>
            <Budget
              diff={summary?.budget?.diff}
              trend={summary?.budget?.trend}
              sx={{ height: '100%' }}
              value={typeof summary?.budget === 'object' ? summary?.budget?.value : summary?.budget ?? '$0'}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalCustomers
              diff={summary?.totalCustomers?.diff}
              trend={summary?.totalCustomers?.trend}
              sx={{ height: '100%' }}
              value={typeof summary?.totalCustomers === 'object' ? summary?.totalCustomers?.value : summary?.totalCustomers ?? '0'}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TasksProgress
              sx={{ height: '100%' }}
              value={typeof summary?.tasksProgress === 'object' ? summary?.tasksProgress?.value ?? 0 : summary?.tasksProgress ?? 0}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalProfit
              sx={{ height: '100%' }}
              value={typeof summary?.totalProfit === 'object' ? summary?.totalProfit?.value : summary?.totalProfit ?? '$0'}
            />
          </Grid>
          <Grid xs={12} lg={8}>
            <Sales
              chartSeries={summary?.sales?.chartSeries ?? summary?.sales ?? []}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <Traffic
              chartSeries={summary?.traffic?.chartSeries ?? summary?.traffic ?? []}
              labels={summary?.traffic?.labels ?? []}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <LatestProducts
              products={products}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={12} lg={8}>
            <LatestOrders
              orders={orders}
              sx={{ height: '100%' }}
            />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
