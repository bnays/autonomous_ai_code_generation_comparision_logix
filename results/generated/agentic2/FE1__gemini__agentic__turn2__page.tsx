'use client';

import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid';

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
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted) {
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
        <CircularProgress size={40} />
      </Box>
    );
  }

  const recentProducts = summary?.recentProducts ?? summary?.products ?? [];
  const recentTransactions = summary?.recentTransactions ?? summary?.orders ?? [];

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

  const salesProps = Array.isArray(summary?.sales)
    ? { chartSeries: summary.sales }
    : typeof summary?.sales === 'object' && summary?.sales !== null
    ? summary.sales
    : { chartSeries: summary?.sales };

  const trafficProps = Array.isArray(summary?.traffic)
    ? { chartSeries: summary.traffic }
    : typeof summary?.traffic === 'object' && summary?.traffic !== null
    ? summary.traffic
    : { chartSeries: summary?.traffic };

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
          <Grid item xs={12} sm={6} lg={3}>
            <Budget sx={{ height: '100%' }} {...budgetProps} />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <TotalCustomers sx={{ height: '100%' }} {...totalCustomersProps} />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <TasksProgress sx={{ height: '100%' }} {...tasksProgressProps} />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <TotalProfit sx={{ height: '100%' }} {...totalProfitProps} />
          </Grid>
          <Grid item xs={12} lg={8}>
            <Sales sx={{ height: '100%' }} {...salesProps} />
          </Grid>
          <Grid item xs={12} md={6} lg={4}>
            <Traffic sx={{ height: '100%' }} {...trafficProps} />
          </Grid>
          <Grid item xs={12} md={6} lg={4}>
            <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
          </Grid>
          <Grid item xs={12} md={12} lg={8}>
            <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
