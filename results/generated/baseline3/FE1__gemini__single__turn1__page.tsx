'use client';

import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchSummary() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted && data) {
          setSummary(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to load dashboard summary');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchSummary();

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
          minHeight: '400px',
          height: '100%',
          width: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const recentProducts = summary?.recentProducts ?? summary?.products ?? [];
  const recentOrders =
    summary?.recentOrders ?? summary?.recentTransactions ?? summary?.orders ?? [];

  const budgetProps =
    typeof summary?.budget === 'object' && summary?.budget !== null
      ? summary.budget
      : { value: summary?.budget };

  const totalCustomersProps =
    typeof summary?.totalCustomers === 'object' && summary?.totalCustomers !== null
      ? summary.totalCustomers
      : { value: summary?.totalCustomers };

  const tasksProgressProps =
    typeof summary?.tasksProgress === 'object' && summary?.tasksProgress !== null
      ? summary.tasksProgress
      : { value: summary?.tasksProgress };

  const totalProfitProps =
    typeof summary?.totalProfit === 'object' && summary?.totalProfit !== null
      ? summary.totalProfit
      : { value: summary?.totalProfit };

  const salesProps =
    typeof summary?.sales === 'object' && summary?.sales !== null && !Array.isArray(summary.sales)
      ? summary.sales
      : { chartSeries: summary?.sales || [] };

  const trafficProps =
    typeof summary?.traffic === 'object' && summary?.traffic !== null && !Array.isArray(summary.traffic)
      ? summary.traffic
      : { chartSeries: summary?.traffic || [], labels: summary?.trafficLabels || [] };

  return (
    <Box component="main" sx={{ flexGrow: 1, py: 8 }}>
      <Container maxWidth="xl">
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}
        <Grid container spacing={3}>
          <Grid item lg={3} sm={6} xs={12}>
            <Budget sx={{ height: '100%' }} {...budgetProps} />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TotalCustomers sx={{ height: '100%' }} {...totalCustomersProps} />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TasksProgress sx={{ height: '100%' }} {...tasksProgressProps} />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TotalProfit sx={{ height: '100%' }} {...totalProfitProps} />
          </Grid>
          <Grid item lg={8} xs={12}>
            <Sales sx={{ height: '100%' }} {...salesProps} />
          </Grid>
          <Grid item lg={4} md={6} xs={12}>
            <Traffic sx={{ height: '100%' }} {...trafficProps} />
          </Grid>
          <Grid item lg={4} md={6} xs={12}>
            <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
          </Grid>
          <Grid item lg={8} md={12} xs={12}>
            <LatestOrders orders={recentOrders} sx={{ height: '100%' }} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
