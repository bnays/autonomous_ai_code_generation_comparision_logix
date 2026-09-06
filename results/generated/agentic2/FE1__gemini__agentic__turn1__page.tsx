'use client';

import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Unstable_Grid2';

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

  const budgetData =
    typeof summary?.budget === 'object' && summary?.budget !== null
      ? summary.budget
      : { value: summary?.budget };

  const totalCustomersData =
    typeof summary?.totalCustomers === 'object' && summary?.totalCustomers !== null
      ? summary.totalCustomers
      : { value: summary?.totalCustomers };

  const tasksProgressData =
    typeof summary?.tasksProgress === 'object' && summary?.tasksProgress !== null
      ? summary.tasksProgress
      : { value: summary?.tasksProgress };

  const totalProfitData =
    typeof summary?.totalProfit === 'object' && summary?.totalProfit !== null
      ? summary.totalProfit
      : { value: summary?.totalProfit };

  const salesData =
    typeof summary?.sales === 'object' && summary?.sales !== null
      ? summary.sales
      : { chartSeries: summary?.sales };

  const trafficData =
    typeof summary?.traffic === 'object' && summary?.traffic !== null
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
          <Grid xs={12} sm={6} lg={3}>
            <Budget sx={{ height: '100%' }} {...budgetData} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalCustomers sx={{ height: '100%' }} {...totalCustomersData} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TasksProgress sx={{ height: '100%' }} {...tasksProgressData} />
          </Grid>
          <Grid xs={12} sm={6} lg={3}>
            <TotalProfit sx={{ height: '100%' }} {...totalProfitData} />
          </Grid>
          <Grid xs={12} lg={8}>
            <Sales sx={{ height: '100%' }} {...salesData} />
          </Grid>
          <Grid xs={12} md={6} lg={4}>
            <Traffic sx={{ height: '100%' }} {...trafficData} />
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
