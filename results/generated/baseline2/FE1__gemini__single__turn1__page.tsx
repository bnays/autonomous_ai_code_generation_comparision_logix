'use client';

import React, { useEffect, useState } from 'react';
import { Box, Container, Unstable_Grid2 as Grid, CircularProgress, Typography } from '@mui/material';
import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

export default function Page() {
  const [summaryData, setSummaryData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted) {
          setSummaryData(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to load dashboard summary');
        }
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
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error" variant="h6">
          {error}
        </Typography>
      </Box>
    );
  }

  const recentProducts = summaryData?.recentProducts ?? [];
  const recentTransactions = summaryData?.recentTransactions ?? summaryData?.recentOrders ?? [];

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
              diff={summaryData?.budget?.diff}
              trend={summaryData?.budget?.trend}
              sx={{ height: '100%' }}
              value={summaryData?.budget?.value ?? summaryData?.budget ?? '$0'}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalCustomers
              diff={summaryData?.totalCustomers?.diff}
              trend={summaryData?.totalCustomers?.trend}
              sx={{ height: '100%' }}
              value={summaryData?.totalCustomers?.value ?? summaryData?.totalCustomers ?? '0'}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TasksProgress
              sx={{ height: '100%' }}
              value={summaryData?.tasksProgress?.value ?? summaryData?.tasksProgress ?? 0}
            />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalProfit
              sx={{ height: '100%' }}
              value={summaryData?.totalProfit?.value ?? summaryData?.totalProfit ?? '$0'}
            />
          </Grid>
          <Grid xs={12} lg={8}>
            <Sales
              chartSeries={summaryData?.sales?.chartSeries ?? summaryData?.salesSeries ?? []}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <Traffic
              chartSeries={summaryData?.traffic?.chartSeries ?? summaryData?.trafficSeries ?? []}
              labels={summaryData?.traffic?.labels ?? []}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <LatestProducts
              products={recentProducts}
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid xs={12} md={12} lg={8}>
            <LatestOrders
              orders={recentTransactions}
              sx={{ height: '100%' }}
            />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
